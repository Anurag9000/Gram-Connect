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

DATASET_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DEFAULT_MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "model.pkl"))
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

# --- In-Memory State & Data Loading ---
# We use in-memory lists to simulate a database for this session.
# In a real app, this would be replaced by SQL queries.

PROBLEMS: List[Dict[str, Any]] = []
VOLUNTEERS: List[Dict[str, Any]] = []

def load_initial_data():
    """Loads mock data and combines it with CSV data."""
    global PROBLEMS, VOLUNTEERS
    
    # Load foundational mocks
    PROBLEMS = get_mock_problems()
    VOLUNTEERS = get_mock_volunteers()
    
    # Load persisted proposals from CSV
    if os.path.exists(DEFAULT_PROPOSALS_CSV):
        try:
            with open(DEFAULT_PROPOSALS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Check if already exists (mock data might duplicate IDs if not careful, 
                    # but here we assume CSV has user-submitted ones with unique IDs)
                    p_id = row.get("proposal_id")
                    if any(p["id"] == p_id for p in PROBLEMS):
                        continue
                        
                    # Convert CSV row to Problem structure
                    PROBLEMS.append({
                        "id": p_id,
                        "villager_id": "anon-villager",
                        "title": row.get("title", "Untitled Issue") if "title" in row else row.get("text", "Issue").split(":")[0],
                        "description": row.get("text", ""),
                        "category": "others", # Default
                        "village_name": row.get("village", "Unknown"),
                        "status": "pending",
                        "lat": 0.0,
                        "lng": 0.0,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "profiles": {
                            "id": "anon-villager",
                            "full_name": "Community Member",
                            "role": "villager",
                        },
                        "matches": []
                    })
        except Exception as e:
            logger.error(f"Failed to load CSV data: {e}")

# Load data on startup (or module import)
load_initial_data()


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
    # Return the current in-memory state
    return PROBLEMS

@app.get("/volunteers")
async def get_volunteers():
    return VOLUNTEERS

@app.get("/volunteer/{volunteer_id}")
async def get_volunteer(volunteer_id: str):
    # Find in in-memory list
    for v in VOLUNTEERS:
        if v["user_id"] == volunteer_id or v["id"] == volunteer_id:
            return v
    # Fallback / Mock
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
    # Update in-memory
    user_id = data.get("user_id")
    for v in VOLUNTEERS:
        if v["user_id"] == user_id:
            v.update(data)
            return {"status": "success", "data": v}
            
    # If not found, create new
    VOLUNTEERS.append(data)
    return {"status": "success", "data": data}

@app.get("/volunteer-tasks")
async def get_volunteer_tasks(volunteer_id: str):
    # Filter problems where matches contain this volunteer
    tasks = []
    for p in PROBLEMS:
        if not p.get("matches"): continue
        for m in p["matches"]:
            if m.get("volunteer_id") == volunteer_id or m.get("volunteers", {}).get("user_id") == volunteer_id:
                 tasks.append({
                    "id": p["id"],
                    "title": p["title"],
                    "village": p["village_name"],
                    "location": p.get("village_address") or p["village_name"],
                    "status": "assigned",
                    "description": p["description"],
                    "assigned_at": m.get("assigned_at", datetime.now().isoformat()),
                })
    return tasks

@app.post("/problems/{problem_id}/assign")
async def assign_task(problem_id: str, payload: Dict[str, str]):
    volunteer_id = payload.get("volunteer_id")
    if not volunteer_id:
        raise HTTPException(status_code=400, detail="volunteer_id is required")

    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    volunteer = next((v for v in VOLUNTEERS if v["id"] == volunteer_id or v["user_id"] == volunteer_id), None)
    if not volunteer:
        print(f"Volunteer {volunteer_id} not found in memory, continuing with mock data...")
        # In a real app we'd error, but here we might just construct a mock match for robustness
        volunteer = {
            "id": volunteer_id,
            "full_name": "Assigned Volunteer", 
            "email": "volunteer@example.com"
        }

    # Add match
    match = {
        "id": f"match-{len(problem.get('matches', [])) + 1}-{int(datetime.now().timestamp())}",
        "problem_id": problem_id,
        "volunteer_id": volunteer_id,
        "assigned_at": datetime.now().isoformat(),
        "completed_at": None,
        "notes": "Assigned via Coordinator Dashboard",
        "volunteers": volunteer
    }
    
    if "matches" not in problem:
        problem["matches"] = []
    problem["matches"].append(match)
    
    # Update problem status to in_progress if it was pending
    if problem["status"] == "pending":
        problem["status"] = "in_progress"

    return {"status": "success", "match": match}


@app.put("/problems/{problem_id}/status")
async def update_problem_status(problem_id: str, payload: Dict[str, str]):
    new_status = payload.get("status")
    if not new_status:
         raise HTTPException(status_code=400, detail="status is required")
         
    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
        
    problem["status"] = new_status
    if new_status == "completed":
        # Mark matches as completed? Optional logic
        pass
        
    return {"status": "success", "problem": problem}


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

# Global lock for CSV writing to ensure thread safety
import threading
csv_lock = threading.Lock()

@app.post("/submit-problem")
async def submit_problem_endpoint(request: ProblemRequest):
    try:
        new_id = f"prob-{int(datetime.now().timestamp())}"
        
        # 1. Update in-memory state
        new_problem = {
            "id": new_id,
            "villager_id": request.coordinator_id or "anon",
            "title": request.title,
            "description": request.description,
            "category": request.category,
            "village_name": request.village_name,
            "status": "pending",
            "lat": 0.0, 
            "lng": 0.0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "profiles": {
                "id": request.coordinator_id or "anon",
                "full_name": "Coordinator",
                "role": "coordinator"
            },
            "matches": []
        }
        PROBLEMS.append(new_problem)

        # 2. Persist to CSV
        with csv_lock:
            file_exists = os.path.exists(DEFAULT_PROPOSALS_CSV)
            with open(DEFAULT_PROPOSALS_CSV, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["proposal_id", "text", "village"])
                
                text_content = f"{request.title}: {request.description} ({request.category})"
                text_content = text_content.replace("\n", " ").replace("\r", "")
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
            # Auto-cleanup temp file is handled by finally
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
    # Clean startup log
    print("Starting SocialCode Backend Server...")
    print(f"Loading data from: {DATASET_ROOT}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
