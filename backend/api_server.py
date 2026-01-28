import os
import logging
import csv
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import shutil
import tempfile

from m3_trainer import TrainingConfig, train_model
from m3_recommend import RecommendationConfig
from recommender_service import RecommenderService
from multimodal_service import transcribe_audio, analyze_image
from notification_service import notify_team_assignment
from mock_data import get_mock_problems, get_mock_volunteers, get_mock_volunteer_tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("api_server")

DATASET_ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
DEFAULT_PEOPLE_CSV = os.path.join(DATASET_ROOT, "people.csv")
DEFAULT_PROPOSALS_CSV = os.path.join(DATASET_ROOT, "proposals.csv")
DEFAULT_PAIRS_CSV = os.path.join(DATASET_ROOT, "pairs.csv")
DEFAULT_VILLAGE_LOCATIONS = os.path.join(DATASET_ROOT, "village_locations.csv")
DEFAULT_DISTANCE_CSV = os.path.join(DATASET_ROOT, "village_distances.csv")

# Initialize Service
recommender_service = RecommenderService(
    model_path=DEFAULT_MODEL_PATH,
    people_csv=DEFAULT_PEOPLE_CSV,
    dataset_root=DATASET_ROOT
)

app = FastAPI(title="SocialCode Backend Service")

# CORS Configuration
# Allow user to specify origins via env var, otherwise default to lenient for dev
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TrainRequest(BaseModel):
    proposals: Optional[str] = None
    people: Optional[str] = None
    pairs: Optional[str] = None
    out: Optional[str] = None
    model_name: Optional[str] = None
    village_locations: Optional[str] = None
    village_distances: Optional[str] = None
    distance_scale: float = 50.0
    distance_decay: float = 30.0


class TrainResponse(BaseModel):
    status: str
    auc: Optional[float]
    model_path: str


class ProblemRequest(BaseModel):
    title: str
    description: str
    category: str
    village_name: str
    village_address: Optional[str] = None
    coordinator_id: str
    visual_tags: Optional[List[str]] = []
    has_audio: Optional[bool] = False


class RecommendRequest(BaseModel):
    proposal_text: str
    village_name: Optional[str] = Field(None, description="Override village name if the text does not mention it explicitly")
    task_start: datetime
    task_end: datetime
    team_size: Optional[int] = Field(None, ge=1)
    num_teams: Optional[int] = Field(10, ge=1)
    severity: Optional[str] = Field(None, pattern="^(LOW|NORMAL|HIGH)$")
    required_skills: Optional[List[str]] = None
    auto_extract: bool = True
    threshold: float = 0.25
    weekly_quota: float = 5.0
    overwork_penalty: float = 0.1
    soft_cap: int = 6
    topk_swap: int = 10
    k_robust: int = 1
    lambda_red: float = 1.0
    lambda_size: float = 1.0
    lambda_will: float = 0.5
    size_buckets: Optional[str] = None
    model_path: Optional[str] = DEFAULT_MODEL_PATH
    people_csv: Optional[str] = DEFAULT_PEOPLE_CSV
    schedule_csv: Optional[str] = None
    village_locations: Optional[str] = DEFAULT_VILLAGE_LOCATIONS
    distance_csv: Optional[str] = DEFAULT_DISTANCE_CSV
    distance_scale: float = 50.0
    distance_decay: float = 30.0
    tau: float = 0.35
    # Hybrid Multimodal extensions
    transcription: Optional[str] = None
    visual_tags: Optional[List[str]] = None


class RecommendResponse(BaseModel):
    severity_detected: str
    severity_source: str
    proposal_location: Optional[str]
    teams: List[dict]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/train", response_model=TrainResponse)
def train_endpoint(request: TrainRequest):
    config = TrainingConfig(
        proposals=request.proposals or DEFAULT_PROPOSALS_CSV,
        people=request.people or DEFAULT_PEOPLE_CSV,
        pairs=request.pairs or DEFAULT_PAIRS_CSV,
        out=request.out or DEFAULT_MODEL_PATH,
        model_name=request.model_name or "sentence-transformers/all-MiniLM-L6-v2",
        village_locations=request.village_locations or DEFAULT_VILLAGE_LOCATIONS,
        village_distances=request.village_distances or DEFAULT_DISTANCE_CSV,
        distance_scale=request.distance_scale,
        distance_decay=request.distance_decay,
    )
    try:
        auc = train_model(config)
        return TrainResponse(status="ok", auc=auc, model_path=config.out)
    except FileNotFoundError as e:
        logger.error(f"Training file not found: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        logger.exception("Training failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/problems")
async def get_problems():
    # In a real scenario, this would read from DB or merged CSV
    # For now, we return mock data plus we could read newly added rows from a CSV if we wanted
    return get_mock_problems()

@app.get("/volunteers")
async def get_volunteers():
    return get_mock_volunteers()

@app.get("/volunteer/{volunteer_id}")
async def get_volunteer(volunteer_id: str):
    # Mock finding a volunteer
    return {
        "id": "vol-profile-id",
        "user_id": volunteer_id,
        "skills": ["Teaching", "Digital Literacy"],
        "availability_status": "available",
        "created_at": datetime.now().isoformat(),
    }

@app.post("/volunteer")
async def update_volunteer(data: Dict[str, Any]):
    logger.info(f"Volunteer profile updated for {data.get('user_id')}")
    return {"status": "success", "data": data}

@app.get("/volunteer-tasks")
async def get_volunteer_tasks(volunteer_id: str):
    return get_mock_volunteer_tasks()

@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(request: RecommendRequest):
    try:
        results = recommender_service.generate_recommendations(request.dict())
        
        # Notify teams if recommendations were generated
        if results and results.get("teams"):
            logger.info("Triggering notifications for assigned teams...")
            notify_team_assignment(
                results["teams"], 
                request.proposal_text or "Village Issue", 
                request.village_name or "Village"
            )

        return RecommendResponse(**results)
    except ValueError as ve:
        logger.error(f"Recommendation validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception("Recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/submit-problem")
async def submit_problem_endpoint(request: ProblemRequest):
    try:
        # Persist to CSV
        file_exists = os.path.exists(DEFAULT_PROPOSALS_CSV)
        new_id = f"prob-{int(datetime.now().timestamp())}"
        
        with open(DEFAULT_PROPOSALS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                # Write header if new file (matching standard fields)
                writer.writerow(["proposal_id", "text", "village"])
            
            # Sanitizing text to avoid CSV injection or formatting issues
            text_content = f"{request.title}: {request.description} ({request.category})"
            writer.writerow([new_id, text_content, request.village_name])
            
        logger.info(f"Problem submitted and saved: {request.title} in {request.village_name}")
        return {"status": "success", "id": new_id}
    except Exception as exc:
        logger.exception("Problem submission failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/transcribe")
def transcribe_endpoint(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        try:
            text = transcribe_audio(tmp_path)
            return {"text": text}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail="Transcription service error")

@app.post("/analyze-image")
def analyze_image_endpoint(file: UploadFile = File(...), labels: Optional[str] = None):
    # labels is passed as a comma-separated string if from form-data
    candidate_labels = labels.split(",") if (labels and labels.strip()) else None
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        result = analyze_image(tmp_path, candidate_labels)
        return result
    except Exception as exc:
        logger.exception("Image analysis failed")
        raise HTTPException(status_code=500, detail="Image analysis service error")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
