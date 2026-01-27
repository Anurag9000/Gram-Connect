import os
import logging
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; refine for production
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
    except Exception as exc:
        logger.exception("Training failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/problems")
async def get_problems():
    # Mock data to match what the frontend expected
    return [
        {
            "id": "problem-1",
            "villager_id": "villager-1",
            "title": "Broken Well Pump",
            "description": "The main well pump is broken and needs repair.",
            "category": "infrastructure",
            "village_name": "Test Village",
            "status": "pending",
            "lat": 21.1458,
            "lng": 79.0882,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "villager-1", 
                "full_name": "Submitted by Coordinator", 
                "email": "anon@test.com", 
                "role": "villager", 
                "created_at": datetime.now().isoformat(), 
                "phone": None 
            },
            "matches": []
        },
        {
            "id": "problem-2",
            "villager_id": "villager-2",
            "title": "Digital Literacy Class",
            "description": "Need someone to teach basic computer skills to children.",
            "category": "digital",
            "village_name": "Other Village",
            "status": "in_progress",
            "lat": 21.1610,
            "lng": 79.0720,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "villager-2", 
                "full_name": "Submitted by Coordinator", 
                "email": "jane@test.com", 
                "role": "villager", 
                "created_at": datetime.now().isoformat(), 
                "phone": None 
            },
            "matches": [
                {
                    "id": "match-1",
                    "problem_id": "problem-2",
                    "volunteer_id": "vol-1",
                    "assigned_at": datetime.now().isoformat(),
                    "completed_at": None,
                    "notes": "Assigned to Test Volunteer",
                    "volunteers": {
                        "id": "vol-1",
                        "user_id": "mock-volunteer-uuid",
                        "skills": ["Teaching", "Digital Literacy"],
                        "availability_status": "available",
                        "created_at": datetime.now().isoformat(),
                        "profiles": { 
                            "id": "mock-volunteer-uuid", 
                            "full_name": "Test Volunteer", 
                            "email": "volunteer@test.com", 
                            "role": "volunteer", 
                            "created_at": datetime.now().isoformat(), 
                            "phone": "1234567890" 
                        }
                    }
                }
            ]
        }
    ]

@app.get("/volunteers")
async def get_volunteers():
    return [
        {
            "id": "vol-1",
            "user_id": "mock-volunteer-uuid",
            "skills": ["Teaching", "Digital Literacy", "Web Development"],
            "availability_status": "available",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-volunteer-uuid", 
                "full_name": "Test Volunteer", 
                "email": "volunteer@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "1234567890" 
            }
        },
        {
            "id": "vol-2",
            "user_id": "mock-vol-2-uuid",
            "skills": ["Plumbing", "Construction"],
            "availability_status": "available",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-vol-2-uuid", 
                "full_name": "Skilled Sam", 
                "email": "sam@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "2345678901" 
            }
        },
        {
            "id": "vol-3",
            "user_id": "mock-vol-3-uuid",
            "skills": ["Electrical Work", "Plumbing"],
            "availability_status": "available",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-vol-3-uuid", 
                "full_name": "Electrician Alice", 
                "email": "alice@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "3456789012" 
            }
        },
        {
            "id": "vol-4",
            "user_id": "mock-vol-4-uuid",
            "skills": ["Agriculture", "Healthcare"],
            "availability_status": "busy",
            "created_at": datetime.now().isoformat(),
            "profiles": { 
                "id": "mock-vol-4-uuid", 
                "full_name": "Doctor Dave", 
                "email": "dave@test.com", 
                "role": "volunteer", 
                "created_at": datetime.now().isoformat(), 
                "phone": "4567890123" 
            }
        }
    ]

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
    # Mock assignments for the volunteer
    return [
        {
            "id": 'task-1',
            "title": 'Broken Well Pump',
            "village": 'Gram Puram',
            "location": 'Near Primary School',
            "status": 'assigned',
            "description": 'The handle of the hand-pump is broken. Needs basic welding or part replacement.',
            "assigned_at": (datetime.now() - timedelta(days=2)).isoformat(),
        }
    ]

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
    except Exception as exc:
        logger.exception("Recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/submit-problem")
async def submit_problem_endpoint(request: ProblemRequest):
    try:
        # In a real app, this would save to a database.
        # For this demo, we'll just log it.
        logger.info(f"Problem submitted: {request.title} in {request.village_name}")
        return {"status": "success", "id": f"prob-{int(datetime.now().timestamp())}"}
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
        raise HTTPException(status_code=500, detail=str(exc))

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
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
