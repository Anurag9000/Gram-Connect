import os
import logging
import csv
import json
import threading
from datetime import datetime
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
from path_utils import (
    ensure_runtime_dir,
    get_repo_paths,
    resolve_distance_csv,
    resolve_model_path,
    resolve_pairs_csv,
    resolve_people_csv,
    resolve_proposals_csv,
    resolve_village_locations_csv,
)
from utils import get_any, read_csv_norm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("api_server")

PATHS = get_repo_paths()
DATASET_ROOT = str(PATHS.data_dir.resolve())
DEFAULT_MODEL_PATH = resolve_model_path()
DEFAULT_PEOPLE_CSV = resolve_people_csv()
DEFAULT_PROPOSALS_CSV = resolve_proposals_csv()
DEFAULT_PAIRS_CSV = resolve_pairs_csv()
DEFAULT_VILLAGE_LOCATIONS = resolve_village_locations_csv()
DEFAULT_DISTANCE_CSV = resolve_distance_csv()
ensure_runtime_dir()
RUNTIME_STATE_JSON = str((PATHS.runtime_dir / "app_state.json").resolve())
RUNTIME_PROFILES_CSV = str((PATHS.data_dir / "runtime_profiles.csv").resolve())

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
    visual_tags: List[str] = Field(default_factory=list)
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
csv_lock = threading.Lock()


def _coerce_visual_tags(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(tag).strip() for tag in parsed if str(tag).strip()]
        return [part.strip() for part in stripped.split(",") if part.strip()]
    return []


def _now_iso() -> str:
    return datetime.now().isoformat()


def _split_items(value: Any, separator: str = ";") -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value or "").strip()
    if not raw:
        return []
    if separator in raw:
        return [item.strip() for item in raw.split(separator) if item.strip()]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _seed_timestamp(index: int) -> str:
    return datetime(2026, 3, 1, 9, 0, 0).replace(hour=9 + (index % 8)).isoformat()


def _load_profile_directory() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(RUNTIME_PROFILES_CSV):
        return {}
    profiles: Dict[str, Dict[str, Any]] = {}
    for row in read_csv_norm(RUNTIME_PROFILES_CSV):
        profile_id = get_any(row, ["id"])
        if not profile_id:
            continue
        profiles[profile_id] = {
            "id": profile_id,
            "email": get_any(row, ["email"]),
            "full_name": get_any(row, ["full_name", "name"], "User"),
            "phone": get_any(row, ["phone"]),
            "role": get_any(row, ["role"], "volunteer"),
            "created_at": _now_iso(),
        }
    return profiles


def _build_seed_volunteers(profile_directory: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    volunteers: List[Dict[str, Any]] = []
    for index, row in enumerate(read_csv_norm(DEFAULT_PEOPLE_CSV)):
        volunteer_id = get_any(row, ["person_id", "student_id", "id"])
        if not volunteer_id:
            continue
        user_id = get_any(row, ["user_id"], volunteer_id)
        profile = profile_directory.get(user_id, {
            "id": user_id,
            "email": get_any(row, ["email"]),
            "full_name": get_any(row, ["name"], volunteer_id),
            "phone": get_any(row, ["phone"]),
            "role": "volunteer",
            "created_at": _seed_timestamp(index),
        })
        volunteers.append({
            "id": volunteer_id,
            "user_id": user_id,
            "skills": _split_items(get_any(row, ["skills", "text"], "")),
            "availability_status": get_any(row, ["availability_status"], "available"),
            "availability": get_any(row, ["availability"], ""),
            "home_location": get_any(row, ["home_location", "location", "village"], ""),
            "created_at": _seed_timestamp(index),
            "updated_at": _seed_timestamp(index),
            "profiles": profile,
        })
    return volunteers


def _build_seed_problems(
    profile_directory: Dict[str, Dict[str, Any]],
    volunteers_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    coordinator_profile = profile_directory.get("mock-coordinator-uuid", {
        "id": "mock-coordinator-uuid",
        "email": "coordinator@test.com",
        "full_name": "Test Coordinator",
        "phone": "0987654321",
        "role": "coordinator",
        "created_at": _now_iso(),
    })
    village_coords = {
        "Sundarpur": (21.1458, 79.0882),
        "Nirmalgaon": (20.9504, 78.9671),
        "Lakshmipur": (23.2156, 77.0854),
        "Devnagar": (23.0105, 77.4212),
        "Riverbend": (21.2514, 81.6296),
    }
    problems: List[Dict[str, Any]] = []
    for index, row in enumerate(read_csv_norm(DEFAULT_PROPOSALS_CSV)):
        problem_id = get_any(row, ["proposal_id", "id"])
        if not problem_id:
            continue
        status = get_any(row, ["status"], "pending")
        created_at = _seed_timestamp(index)
        village_name = get_any(row, ["village", "village_name"], "Unknown")
        lat, lng = village_coords.get(village_name, (0.0, 0.0))
        matches = []
        for match_index, volunteer_id in enumerate(_split_items(get_any(row, ["seed_assignees"], ""))):
            volunteer = volunteers_by_id.get(volunteer_id)
            if not volunteer:
                continue
            assigned_at = _seed_timestamp(index + match_index + 1)
            matches.append({
                "id": f"seed-match-{problem_id}-{match_index + 1}",
                "problem_id": problem_id,
                "volunteer_id": volunteer_id,
                "assigned_at": assigned_at,
                "completed_at": assigned_at if status == "completed" else None,
                "notes": "Seeded canonical assignment",
                "volunteers": volunteer,
            })
        problems.append({
            "id": problem_id,
            "villager_id": coordinator_profile["id"],
            "title": get_any(row, ["title"], "Untitled Issue"),
            "description": get_any(row, ["text", "description"], ""),
            "category": get_any(row, ["category"], "others"),
            "village_name": village_name,
            "village_address": get_any(row, ["village_address"]),
            "visual_tags": _coerce_visual_tags(get_any(row, ["visual_tags"], "")),
            "has_audio": str(get_any(row, ["has_audio"], "")).strip().lower() in {"1", "true", "yes"},
            "status": status,
            "lat": lat,
            "lng": lng,
            "created_at": created_at,
            "updated_at": created_at,
            "profiles": coordinator_profile,
            "matches": matches,
        })
    return problems


def persist_runtime_state() -> None:
    with csv_lock:
        with open(RUNTIME_STATE_JSON, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "problems": PROBLEMS,
                    "volunteers": VOLUNTEERS,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )


def _match_targets_volunteer(match: Dict[str, Any], volunteer_id: str) -> bool:
    volunteer = match.get("volunteers", {})
    return (
        match.get("volunteer_id") == volunteer_id
        or volunteer.get("user_id") == volunteer_id
        or volunteer.get("id") == volunteer_id
    )


def load_initial_data(force_seed: bool = False):
    """Loads seeded runtime state backed by canonical CSV data."""
    global PROBLEMS, VOLUNTEERS

    if os.path.exists(RUNTIME_STATE_JSON) and not force_seed:
        try:
            with open(RUNTIME_STATE_JSON, "r", encoding="utf-8") as handle:
                state = json.load(handle)
            PROBLEMS = list(state.get("problems", []))
            VOLUNTEERS = list(state.get("volunteers", []))
            if PROBLEMS and VOLUNTEERS:
                return
        except Exception as exc:
            logger.warning("Failed to load runtime state, rebuilding from canonical dataset: %s", exc)

    try:
        profile_directory = _load_profile_directory()
        VOLUNTEERS = _build_seed_volunteers(profile_directory)
        volunteers_by_id = {volunteer["id"]: volunteer for volunteer in VOLUNTEERS}
        PROBLEMS = _build_seed_problems(profile_directory, volunteers_by_id)
        persist_runtime_state()
    except Exception as exc:
        logger.error("Failed to load canonical seed data: %s", exc)
        PROBLEMS = []
        VOLUNTEERS = []


def reset_runtime_state() -> None:
    if os.path.exists(RUNTIME_STATE_JSON):
        os.remove(RUNTIME_STATE_JSON)
    load_initial_data(force_seed=True)

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
    return PROBLEMS

@app.get("/volunteers")
async def get_volunteers():
    return VOLUNTEERS

@app.get("/volunteer/{volunteer_id}")
async def get_volunteer(volunteer_id: str):
    for volunteer in VOLUNTEERS:
        if volunteer["user_id"] == volunteer_id or volunteer["id"] == volunteer_id:
            return volunteer

    raise HTTPException(status_code=404, detail="Volunteer profile not found")

@app.post("/volunteer")
async def update_volunteer(data: Dict[str, Any]):
    logger.info(f"Volunteer profile updated for {data.get('user_id')}")
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    timestamp = _now_iso()
    for volunteer in VOLUNTEERS:
        if volunteer.get("user_id") == user_id:
            volunteer.update(data)
            volunteer.setdefault("id", data.get("id") or f"vol-{user_id}")
            volunteer.setdefault("created_at", timestamp)
            volunteer["updated_at"] = timestamp
            persist_runtime_state()
            return {"status": "success", "data": volunteer}

    new_volunteer = {
        "id": data.get("id") or f"vol-{user_id}",
        "user_id": user_id,
        "skills": list(data.get("skills") or []),
        "availability_status": data.get("availability_status") or "available",
        "created_at": timestamp,
        "updated_at": timestamp,
        "profiles": data.get("profiles") or {
            "id": user_id,
            "full_name": data.get("full_name") or "Volunteer",
            "email": data.get("email"),
            "phone": data.get("phone"),
            "role": "volunteer",
            "created_at": timestamp,
        },
    }
    VOLUNTEERS.append(new_volunteer)
    persist_runtime_state()
    return {"status": "success", "data": new_volunteer}

@app.get("/volunteer-tasks")
async def get_volunteer_tasks(volunteer_id: str):
    tasks_by_problem: Dict[str, Dict[str, Any]] = {}
    for problem in PROBLEMS:
        if not problem.get("matches"):
            continue
        for match in problem["matches"]:
            if not _match_targets_volunteer(match, volunteer_id):
                continue
            existing = tasks_by_problem.get(problem["id"])
            assigned_at = match.get("assigned_at", _now_iso())
            if existing and existing["assigned_at"] >= assigned_at:
                continue
            tasks_by_problem[problem["id"]] = {
                "id": problem["id"],
                "title": problem["title"],
                "village": problem["village_name"],
                "location": problem.get("village_address") or problem["village_name"],
                "status": problem.get("status", "assigned"),
                "description": problem["description"],
                "assigned_at": assigned_at,
            }
    return sorted(tasks_by_problem.values(), key=lambda task: task["assigned_at"], reverse=True)

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
        logger.warning("Volunteer %s not found in memory, continuing with fallback data.", volunteer_id)
        volunteer = {
            "id": volunteer_id,
            "full_name": "Assigned Volunteer",
            "email": "volunteer@example.com",
        }

    existing_match = next(
        (match for match in problem.get("matches", []) if _match_targets_volunteer(match, volunteer_id)),
        None,
    )
    if existing_match:
        return {"status": "success", "match": existing_match}

    match = {
        "id": f"match-{len(problem.get('matches', [])) + 1}-{int(datetime.now().timestamp())}",
        "problem_id": problem_id,
        "volunteer_id": volunteer_id,
        "assigned_at": _now_iso(),
        "completed_at": None,
        "notes": "Assigned via Coordinator Dashboard",
        "volunteers": volunteer,
    }

    if "matches" not in problem:
        problem["matches"] = []
    problem["matches"].append(match)

    if problem.get("status") == "pending":
        problem["status"] = "in_progress"
    problem["updated_at"] = _now_iso()
    persist_runtime_state()

    return {"status": "success", "match": match}


@app.put("/problems/{problem_id}/status")
async def update_problem_status(problem_id: str, payload: Dict[str, str]):
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")
    if new_status not in {"pending", "in_progress", "completed"}:
        raise HTTPException(status_code=400, detail="status must be pending, in_progress, or completed")

    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem["status"] = new_status
    problem["updated_at"] = _now_iso()
    if new_status == "completed":
        completed_at = _now_iso()
        for match in problem.get("matches", []):
            match["completed_at"] = match.get("completed_at") or completed_at
    elif new_status in {"pending", "in_progress"}:
        for match in problem.get("matches", []):
            match["completed_at"] = None
    persist_runtime_state()
    return {"status": "success", "problem": problem}


@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(request: RecommendRequest):
    try:
        results = recommender_service.generate_recommendations(request.model_dump())
        
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
        new_id = f"prob-{int(datetime.now().timestamp())}"
        coordinator_profile = _load_profile_directory().get(request.coordinator_id, {
            "id": request.coordinator_id or "anon",
            "full_name": "Coordinator",
            "role": "coordinator",
            "email": None,
            "phone": None,
            "created_at": _now_iso(),
        })
        
        new_problem = {
            "id": new_id,
            "villager_id": request.coordinator_id or "anon",
            "title": request.title,
            "description": request.description,
            "category": request.category,
            "village_name": request.village_name,
            "village_address": request.village_address,
            "visual_tags": request.visual_tags or [],
            "has_audio": bool(request.has_audio),
            "status": "pending",
            "lat": 0.0,
            "lng": 0.0,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "profiles": coordinator_profile,
            "matches": [],
        }
        PROBLEMS.append(new_problem)
        persist_runtime_state()
        logger.info(f"Problem submitted and saved: {request.title} in {request.village_name}")
        return {"status": "success", "id": new_id}
    except Exception as exc:
        logger.exception("Problem submission failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/transcribe")
def transcribe_endpoint(file: UploadFile = File(...)):
    try:
        suffix = os.path.splitext(file.filename or "")[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
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
    print("Starting SocialCode Backend Server...")
    print(f"Loading data from: {DATASET_ROOT}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
