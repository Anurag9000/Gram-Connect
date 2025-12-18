import os
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from m3_trainer import TrainingConfig, train_model
from m3_recommend import RecommendationConfig
from recommender_service import generate_recommendations
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
    out: Optional[str] = DEFAULT_MODEL_PATH
    model_name: Optional[str] = "sentence-transformers/all-MiniLM-L6-v2"
    village_locations: Optional[str] = DEFAULT_VILLAGE_LOCATIONS
    village_distances: Optional[str] = DEFAULT_DISTANCE_CSV
    distance_scale: float = 50.0
    distance_decay: float = 30.0


class TrainResponse(BaseModel):
    status: str
    auc: Optional[float]
    model_path: str


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
async def train_endpoint(request: TrainRequest):
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


@app.post("/recommend", response_model=RecommendResponse)
async def recommend_endpoint(request: RecommendRequest):
    config = RecommendationConfig(
        model=request.model_path or DEFAULT_MODEL_PATH,
        people=request.people_csv or DEFAULT_PEOPLE_CSV,
        proposal_text=request.proposal_text,
        proposal_location_override=request.village_name,
        # Fuse multimodal inputs if present
        transcription=request.transcription,
        visual_tags=request.visual_tags,
        auto_extract=request.auto_extract,
        threshold=request.threshold,
        required_skills=request.required_skills,
        tau=request.tau,
        task_start=request.task_start.isoformat(),
        task_end=request.task_end.isoformat(),
        schedule_csv=request.schedule_csv,
        weekly_quota=request.weekly_quota,
        overwork_penalty=request.overwork_penalty,
        soft_cap=max(request.team_size or 6, 1),
        topk_swap=request.num_teams or 10,
        k_robust=1,
        lambda_red=request.lambda_red,
        lambda_size=request.lambda_size,
        lambda_will=request.lambda_will,
        size_buckets=request.size_buckets,
        team_size=request.team_size,
        num_teams=request.num_teams,
        severity_override=request.severity,
        village_locations=request.village_locations or DEFAULT_VILLAGE_LOCATIONS,
        distance_csv=request.distance_csv or DEFAULT_DISTANCE_CSV,
        distance_scale=request.distance_scale,
        distance_decay=request.distance_decay,
        out=None,
    )
    try:
        results = generate_recommendations(config)
        
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

@app.post("/transcribe")
async def transcribe_endpoint(file_path: str):
    try:
        text = transcribe_audio(file_path)
        return {"text": text}
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/analyze-image")
async def analyze_image_endpoint(file_path: str, labels: Optional[List[str]] = None):
    try:
        result = analyze_image(file_path, labels)
        return result
    except Exception as exc:
        logger.exception("Image analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
