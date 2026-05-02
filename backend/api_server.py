import os
import logging
import csv
import json
import hashlib
import mimetypes
import threading
import uuid
import re
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import shutil
import tempfile
from collections import Counter, defaultdict

from env_loader import load_local_env
from demo_bootstrap import ensure_canonical_dataset, should_bootstrap_models
from postgres_store import PostgresStore
from recommender_service import RecommenderService
from insights_service import (
    analyze_coordinator_query,
    build_insight_overview,
    build_campaign_mode_plan,
    build_hotspot_heatmap,
    build_preventive_maintenance_plan,
    build_root_cause_graph,
    build_seasonal_risk_forecast,
    build_weekly_briefing,
    find_duplicate_problem_candidates,
    infer_problem_triage,
)
from platform_service import (
    answer_policy_question,
    assess_burnout_signals,
    assess_proof_spoofing,
    build_broadcast_feed,
    build_repeat_breakdown_metrics,
    build_resident_feedback_summary,
    autofill_problem_form,
    build_ab_test_plan,
    build_anomaly_dashboard,
    build_announcement_feed,
    build_asset_registry,
    build_audit_pack,
    build_bulk_export_bundle,
    build_budget_forecast,
    build_community_polls,
    build_conversation_memory,
    build_custom_forms_bundle,
    build_district_hierarchy,
    build_impact_measurement,
    build_procurement_tracker,
    build_resident_confirmation,
    build_shift_plan,
    build_skill_certifications,
    build_suggestion_box,
    build_training_mode,
    build_village_champions,
    build_webhook_events,
    build_work_order_templates,
    find_case_similarity_explorer,
)
from multimodal_service import transcribe_audio, analyze_image, verify_resolution_proof, infer_problem_severity, extract_problem_from_whatsapp, suggest_jugaad_fix, suggest_immediate_problem_actions
from notification_service import notify_problem_resolved, notify_problem_follow_up, notify_team_assignment
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

load_local_env()

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
RUNTIME_PEOPLE_CSV = str((PATHS.runtime_dir / "live_people.csv").resolve())
MEDIA_ROOT = PATHS.runtime_dir / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
STATE_VERSION = 0
DATA_STORE = PostgresStore.from_env()
VILLAGE_COORDS_CACHE: Dict[str, tuple[float, float]] = {}

# Initialize Service
recommender_service = RecommenderService(
    model_path=DEFAULT_MODEL_PATH,
    people_csv=DEFAULT_PEOPLE_CSV,
    dataset_root=DATASET_ROOT
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bootstrap the demo runtime on application startup."""
    if should_bootstrap_models():
        try:
            ensure_canonical_dataset()
            reset_runtime_state()
            logger.info("Demo runtime bootstrapped (Nexus engine — no model training required).")
        except Exception as exc:
            logger.exception("Demo bootstrap failed: %s", exc)
    yield


app = FastAPI(title="Gram Connect Backend Service", lifespan=lifespan)

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

app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")


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
    coordinator_id: Optional[str] = None
    villager_id: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None
    visual_tags: List[str] = Field(default_factory=list)
    has_audio: Optional[bool] = False
    media_ids: List[str] = Field(default_factory=list)
    transcript: Optional[str] = None
    transcript_language: Optional[str] = None
    severity: Optional[str] = Field(None, pattern="^(LOW|NORMAL|HIGH)$")


class ProfileRequest(BaseModel):
    id: Optional[str] = None
    email: Optional[str] = None
    full_name: str
    phone: Optional[str] = None
    role: str = Field("villager", pattern="^(villager|volunteer|coordinator|supervisor|partner)$")
    village_name: Optional[str] = None


class ProofRequest(BaseModel):
    volunteer_id: str
    before_media_id: Optional[str] = None
    after_media_id: Optional[str] = None
    notes: Optional[str] = None


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


class InsightChatRequest(BaseModel):
    query: str
    days_back: int = Field(30, ge=1, le=365)
    limit: int = Field(5, ge=1, le=10)


class JugaadRequest(BaseModel):
    problem_id: str
    broken_media_id: str
    materials_media_id: str
    volunteer_id: Optional[str] = None
    notes: Optional[str] = None


class JugaadResponse(BaseModel):
    problem_id: str
    summary: str
    problem_read: str
    observed_broken_part: str
    observed_materials: str
    temporary_fix: str
    step_by_step: List[str]
    safety_notes: List[str]
    materials_to_use: List[str]
    materials_to_avoid: List[str]
    when_to_stop: List[str]
    needs_official_part: bool
    confidence: float
    source: str
    broken_analysis: Optional[Dict[str, Any]] = None
    materials_analysis: Optional[Dict[str, Any]] = None


class ProblemGuidanceRequest(BaseModel):
    title: str
    description: str
    category: Optional[str] = None
    village_name: Optional[str] = None
    transcript: Optional[str] = None
    severity: Optional[str] = Field(None, pattern="^(LOW|NORMAL|HIGH)$")
    visual_tags: List[str] = Field(default_factory=list)


class DuplicateCandidateResponse(BaseModel):
    problem_id: str
    title: Optional[str] = None
    village_name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    distance_km: Optional[float] = None
    score: float
    semantic_score: float
    reason: str
    suggested_action: str


class ProblemGuidanceResponse(BaseModel):
    topic: str
    department: str
    urgency: str
    response_path: str
    summary: str
    what_you_can_do_now: List[str]
    materials_to_find: List[str]
    safety_notes: List[str]
    when_to_stop: List[str]
    best_duration: str
    confidence: float
    source: str
    visual_tags: List[str]
    duplicate_candidates: List[DuplicateCandidateResponse] = Field(default_factory=list)
    similar_problem_count: int = 0
    root_cause_hint: Optional[str] = None


class BroadcastRequest(BaseModel):
    owner_id: Optional[str] = None
    title: str
    message: str
    event_type: str = Field("general")
    audience_type: str = Field("all", pattern="^(all|villages|volunteers)$")
    target_villages: List[str] = Field(default_factory=list)
    target_volunteers: List[str] = Field(default_factory=list)
    target_skills: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    media_ids: List[str] = Field(default_factory=list)
    scheduled_for: Optional[str] = None
    status: Optional[str] = None


class BroadcastRecordResponse(BaseModel):
    id: str
    record_type: str
    subtype: Optional[str] = None
    owner_id: Optional[str] = None
    status: Optional[str] = None
    title: str
    message: str
    event_type: str
    audience_type: str
    tags: List[str]
    target_villages: List[str]
    target_volunteers: List[str]
    target_skills: List[str]
    media_ids: List[str]
    scheduled_for: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BroadcastFeedResponse(BaseModel):
    generated_at: str
    window_days: Optional[int] = None
    scope: str
    summary: str
    items: List[BroadcastRecordResponse]


class ResidentFeedbackAnalyticsResponse(BaseModel):
    generated_at: str
    window_days: int
    summary: str
    total_feedback: int
    response_counts: Dict[str, int]
    average_rating: Optional[float] = None
    volunteers: List[Dict[str, Any]]
    villages: List[Dict[str, Any]]
    recent_feedback: List[Dict[str, Any]]


class RepeatBreakdownVillageResponse(BaseModel):
    village_name: str
    problem_count: int
    open_problem_count: int
    completed_problem_count: int
    repeat_problem_count: int
    repeat_rate: float
    average_gap_days: Optional[float] = None
    average_resolution_hours: Optional[float] = None
    top_topic: str
    topic_breakdown: List[tuple[str, int]]
    latest_problem_at: Optional[str] = None


class RepeatBreakdownResponse(BaseModel):
    generated_at: str
    window_days: int
    summary: str
    villages: List[RepeatBreakdownVillageResponse]
    top_topics: List[tuple[str, int]]
    average_repeat_gap_days: Optional[float] = None


class PublicStatusBoardItem(BaseModel):
    id: str
    title: str
    category: Optional[str] = None
    village_name: Optional[str] = None
    village_address: Optional[str] = None
    status: str
    severity: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    assigned_count: int = 0
    duplicate_count: int = 0
    media_count: int = 0


class PublicStatusBoardResponse(BaseModel):
    generated_at: str
    window_days: int
    village_name: Optional[str] = None
    status_filter: Optional[str] = None
    open_count: int
    in_progress_count: int
    completed_count: int
    total_count: int
    items: List[PublicStatusBoardItem]


class PlaybookResponse(BaseModel):
    id: str
    topic: str
    village_name: Optional[str] = None
    title: str
    summary: str
    materials: List[str]
    safety_notes: List[str]
    steps: List[str]
    source_problem_id: Optional[str] = None
    source_problem_title: Optional[str] = None
    created_at: str


class InventoryItemRequest(BaseModel):
    owner_type: str = Field(pattern="^(village|volunteer|coordinator)$")
    owner_id: str
    item_name: str
    quantity: int = Field(ge=0)
    notes: Optional[str] = None


class InventoryItemResponse(BaseModel):
    id: str
    owner_type: str
    owner_id: str
    item_name: str
    quantity: int
    notes: Optional[str] = None
    updated_at: str


class EscalationResponse(BaseModel):
    generated_at: str
    window_days: int
    overdue_count: int
    items: List[Dict[str, Any]]


class ReputationResponse(BaseModel):
    generated_at: str
    window_days: int
    volunteers: List[Dict[str, Any]]


class RouteOptimizerResponse(BaseModel):
    generated_at: str
    window_days: int
    routes: List[Dict[str, Any]]


class FollowUpFeedbackRequest(BaseModel):
    source: str = Field("public-board", pattern="^(public-board|whatsapp|sms|manual|phone)$")
    response: str = Field(pattern="^(resolved|still_broken|needs_more_help)$")
    note: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None
    volunteer_id: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)


class SeasonalRiskResponse(BaseModel):
    generated_at: str
    window_days: int
    summary: str
    risks: List[Dict[str, Any]]
    top_topics: List[Any] = Field(default_factory=list)
    top_months: List[Any] = Field(default_factory=list)


class MaintenancePlanResponse(BaseModel):
    generated_at: str
    window_days: int
    summary: str
    items: List[Dict[str, Any]]
    top_assets: List[Any] = Field(default_factory=list)


class HeatmapResponse(BaseModel):
    generated_at: str
    window_days: int
    summary: str
    cells: List[Dict[str, Any]]


class CampaignModeResponse(BaseModel):
    generated_at: str
    window_days: int
    summary: str
    campaigns: List[Dict[str, Any]]
    top_topics: List[Any] = Field(default_factory=list)


class EvidenceComparisonResponse(BaseModel):
    generated_at: str
    problem_id: str
    title: str
    status: str
    before_media_id: Optional[str] = None
    after_media_id: Optional[str] = None
    before_url: Optional[str] = None
    after_url: Optional[str] = None
    accepted: bool
    confidence: float
    summary: str
    detected_change: str
    source: str


class PlatformRecordRequest(BaseModel):
    record_id: Optional[str] = None
    subtype: Optional[str] = None
    owner_id: Optional[str] = None
    status: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class ResidentConfirmationRequest(BaseModel):
    source: str = Field("resident", pattern="^(resident|public-board|sms|whatsapp|phone|manual)$")
    response: str = Field(pattern="^(resolved|still_broken|needs_more_help)$")
    note: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None


class ProblemTextRequest(BaseModel):
    text: str
    village_name: Optional[str] = None


class PolicyQuestionRequest(BaseModel):
    question: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/webhooks/whatsapp")
async def whatsapp_webhook(From: str = Form(...), MediaUrl0: str = Form(None), Body: str = Form("")):
    # 1. Identity Resolution
    reporter_phone = From.replace("whatsapp:", "").strip()
    villager_id = f"wa-{hashlib.md5(reporter_phone.encode()).hexdigest()[:8]}"
    reporter_name = "WhatsApp User"
    
    # In a real app we'd look up the phone in RUNTIME_PROFILES_CSV or VOLUNTEERS
    # For now, we auto-create a mock profile
    profile = {
        "id": villager_id,
        "full_name": reporter_name,
        "phone": reporter_phone,
        "role": "villager",
        "created_at": _now_iso()
    }
    _upsert_profile(profile)

    # 2. Multimodal Extraction
    # We would normally download the media from Twilio. Since this is a demo/webhook,
    # we simulate passing the text Body (which might be a transcript if Twilio transcribes)
    # directly to our Gemini extraction.
    extracted_data = extract_problem_from_whatsapp(transcript=Body, image_path=None)

    # 3. Create the problem
    problem_id = f"PROB-WA-{uuid.uuid4().hex[:6].upper()}"
    lat, lng = _village_coordinates(extracted_data["village_name"])
    
    problem = {
        "id": problem_id,
        "villager_id": villager_id,
        "title": extracted_data["title"],
        "description": extracted_data["description"],
        "category": extracted_data["category"],
        "village_name": extracted_data["village_name"],
        "village_address": None,
        "reporter_name": reporter_name,
        "reporter_phone": reporter_phone,
        "visual_tags": [],
        "has_audio": bool(MediaUrl0),
        "status": "pending",
        "lat": lat,
        "lng": lng,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "profiles": profile,
        "severity": extracted_data["severity"]
    }
    
    PROBLEMS.insert(0, problem)
    persist_runtime_state()
    
    # 4. Trigger auto-matching
    payload = _recommendation_payload_for_problem(problem, people_csv=DEFAULT_PEOPLE_CSV)
    try:
        results = recommender_service.generate_recommendations(payload)
        top_team = (results.get("teams") or [{}])[0]
        members = list(top_team.get("members") or [])
        matches = []
        for rank, member in enumerate(members):
            volunteer = _volunteer_lookup_by_candidate_id(member.get("person_id") or member.get("id"))
            if volunteer:
                matches.append(_build_problem_match(problem, volunteer, rank, "Initial WhatsApp Auto-match"))
        if matches:
            problem["matches"] = matches
            problem["status"] = "in_progress"
            problem["updated_at"] = _now_iso()
            _record_learning_event(
                "whatsapp_problem_reported",
                entity_type="problem",
                entity_id=problem_id,
                summary=f"WhatsApp problem reported: {problem_id}",
                payload={"problem": problem, "matches": matches},
                text=" ".join([
                    problem.get("title", ""),
                    problem.get("description", ""),
                    problem.get("category", ""),
                    problem.get("village_name", ""),
                ]),
            )
            persist_runtime_state()
    except Exception as exc:
        logger.warning(f"Auto-match failed for WhatsApp problem {problem_id}: {exc}")

    # 5. Return TwiML response
    twiml = f"<Response><Message>Gram Connect: Issue reported! ID: {problem_id}. We are assigning a volunteer.</Message></Response>"
    from fastapi.responses import Response
    return Response(content=twiml, media_type="text/xml")


@app.get("/villages")
async def list_villages():
    """Return all known villages with coordinates for map autocomplete."""
    try:
        rows = DATA_STORE.get_village_name_rows()
        if not rows:
            rows = read_csv_norm(DEFAULT_VILLAGE_LOCATIONS)
        villages = []
        for r in rows:
            name = get_any(r, ["village_name", "village", "name"])
            lat_raw = get_any(r, ["lat", "latitude"])
            lng_raw = get_any(r, ["lng", "longitude"])
            district = get_any(r, ["district_placeholder", "district"], "")
            state = get_any(r, ["state_placeholder", "state"], "")
            if not name:
                continue
            entry: Dict[str, Any] = {"name": name, "district": district, "state": state}
            if lat_raw and lng_raw:
                try:
                    entry["lat"] = float(lat_raw)
                    entry["lng"] = float(lng_raw)
                except ValueError:
                    pass
            villages.append(entry)
        # Also include any village names that appear in problems but aren't in the CSV
        known_names = {v["name"] for v in villages}
        for p in PROBLEMS:
            vn = p.get("village_name")
            if vn and vn not in known_names:
                lat, lng = _village_coordinates(vn)
                villages.append({"name": vn, "district": "", "state": "", "lat": lat, "lng": lng})
                known_names.add(vn)
        return sorted(villages, key=lambda v: v["name"])
    except Exception as e:
        return []

# --- Runtime State ---
# The in-memory lists are the active request cache.
# Postgres is the source of truth and is synchronized on every write.

PROBLEMS: List[Dict[str, Any]] = []
VOLUNTEERS: List[Dict[str, Any]] = []
PROFILES: List[Dict[str, Any]] = []
MEDIA_ASSETS: List[Dict[str, Any]] = []
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


def _safe_identifier(value: str) -> str:
    cleaned = [ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip()]
    normalized = "".join(cleaned).strip("-")
    return normalized or "asset"


def _village_coordinates(village_name: Optional[str]) -> tuple[float, float]:
    # Primary: canonical coordinates that match generate_canonical_dataset.py exactly
    village_coords: Dict[str, tuple[float, float]] = {
        "Sundarpur":  (21.1458, 79.0882),
        "Nirmalgaon": (20.7453, 78.6022),
        "Lakshmipur": (23.2000, 77.0833),
        "Devnagar":   (23.2599, 77.4126),
        "Riverbend":  (21.2514, 81.6296),
    }
    if VILLAGE_COORDS_CACHE:
        village_coords.update(VILLAGE_COORDS_CACHE)

    try:
        if DATA_STORE:
            for name, coords in DATA_STORE.get_village_coordinates().items():
                village_coords.setdefault(name, coords)
    except Exception:
        pass

    if village_name and village_name in village_coords:
        return village_coords[village_name]

    # Deterministic fallback within India bounding box for unknown villages
    seed = (village_name or "unknown-village").encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    lat_ratio = int(digest[:8], 16) / 0xFFFFFFFF
    lng_ratio = int(digest[8:16], 16) / 0xFFFFFFFF
    lat = 8.0 + (lat_ratio * 29.0)
    lng = 68.0 + (lng_ratio * 29.0)
    return round(lat, 4), round(lng, 4)



def _media_relative_url(path: Path) -> str:
    return f"/media/{path.relative_to(MEDIA_ROOT).as_posix()}"


def _upsert_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = _now_iso()
    profile_id = profile.get("id") or profile.get("user_id") or f"profile-{uuid.uuid4().hex[:12]}"
    normalized = {
        "id": str(profile_id),
        "email": profile.get("email"),
        "full_name": profile.get("full_name") or profile.get("name") or "Resident",
        "phone": profile.get("phone"),
        "role": profile.get("role") or "villager",
        "village_name": profile.get("village_name"),
        "created_at": profile.get("created_at") or timestamp,
        "updated_at": timestamp,
    }

    existing_index = next((index for index, item in enumerate(PROFILES) if str(item.get("id")) == str(profile_id)), None)
    if existing_index is not None:
        merged = {**PROFILES[existing_index], **normalized}
        PROFILES[existing_index] = merged
        return merged

    PROFILES.append(normalized)
    return normalized


def _find_profile(profile_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not profile_id:
        return None
    target = str(profile_id)
    for profile in PROFILES:
        if str(profile.get("id")) == target:
            return profile
    return None


def _asset_by_id(media_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not media_id:
        return None
    target = str(media_id)
    for asset in MEDIA_ASSETS:
        if str(asset.get("id")) == target:
            return asset
    return None


def _serialize_problem(problem: Dict[str, Any]) -> Dict[str, Any]:
    serialized = dict(problem)
    media_ids = list(serialized.get("media_ids") or [])
    serialized["media_assets"] = [asset for asset in (_asset_by_id(media_id) for media_id in media_ids) if asset]
    return serialized


def _serialize_problems(problems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _sort_key(problem: Dict[str, Any]) -> str:
        return str(problem.get("created_at") or "")

    ordered = sorted(problems, key=_sort_key, reverse=True)
    return [_serialize_problem(problem) for problem in ordered]


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _problem_primary_volunteer_id(problem: Dict[str, Any]) -> Optional[str]:
    proof = problem.get("proof") or {}
    proof_volunteer = str(proof.get("volunteer_id") or "").strip()
    if proof_volunteer:
        return proof_volunteer
    matches = problem.get("matches") or []
    for match in reversed(matches):
        candidate = str(
            match.get("volunteer_id")
            or match.get("volunteer", {}).get("id")
            or match.get("volunteers", {}).get("id")
            or ""
        ).strip()
        if candidate:
            return candidate
    return None


def _ensure_problem_media_list(problem: Dict[str, Any]) -> List[str]:
    media_ids = problem.get("media_ids")
    if not isinstance(media_ids, list):
        media_ids = []
    problem["media_ids"] = media_ids
    return media_ids


def _attach_media_to_problem(problem: Dict[str, Any], media_asset: Dict[str, Any]) -> None:
    media_ids = _ensure_problem_media_list(problem)
    media_id = media_asset["id"]
    if media_id not in media_ids:
        media_ids.append(media_id)
    problem["updated_at"] = _now_iso()


def _attach_proof_to_problem(problem: Dict[str, Any], media_asset_ids: List[str], volunteer_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
    proof = dict(problem.get("proof") or {})
    proof["volunteer_id"] = volunteer_id
    proof["before_media_id"] = media_asset_ids[0] if media_asset_ids else proof.get("before_media_id")
    proof["after_media_id"] = media_asset_ids[1] if len(media_asset_ids) > 1 else proof.get("after_media_id")
    proof["media_ids"] = list(media_asset_ids)
    proof["notes"] = notes or proof.get("notes")
    proof["submitted_at"] = _now_iso()
    problem["proof"] = proof
    if media_asset_ids:
        problem["media_ids"] = list(dict.fromkeys(list(problem.get("media_ids") or []) + media_asset_ids))
    problem["status"] = "completed"
    problem["updated_at"] = _now_iso()
    for match in problem.get("matches", []):
        if _match_targets_volunteer(match, volunteer_id):
            match["completed_at"] = _now_iso()
            match["proof"] = proof
            match["proof_media_ids"] = list(media_asset_ids)
            if notes:
                match["notes"] = notes
    return proof


def _verify_problem_proof(problem: Dict[str, Any], request: ProofRequest) -> Dict[str, Any]:
    before_asset = _asset_by_id(request.before_media_id) if request.before_media_id else None
    after_asset = _asset_by_id(request.after_media_id) if request.after_media_id else None
    if not after_asset:
        raise HTTPException(status_code=400, detail="An after image is required for proof verification.")

    try:
        verification = verify_resolution_proof(
            before_asset.get("path") if before_asset else None,
            after_asset.get("path"),
            problem_title=problem.get("title", "Village issue"),
            problem_description=problem.get("description", ""),
            category=problem.get("category"),
            visual_tags=list(problem.get("visual_tags") or []),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Proof verification failed for %s", problem.get("id"))
        raise HTTPException(status_code=502, detail=f"Proof verification failed: {exc}")

    if not verification.get("accepted"):
        raise HTTPException(
            status_code=400,
            detail=verification.get("summary") or "Proof was rejected by Gemini verification.",
        )

    return verification


def _store_media_file(
    file: UploadFile,
    *,
    kind: str,
    problem_id: Optional[str] = None,
    volunteer_id: Optional[str] = None,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    def _normalize_request_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if value.__class__.__module__.startswith("fastapi.params"):
            default = getattr(value, "default", None)
            return None if default is None else str(default)
        return str(value)

    kind = _normalize_request_value(kind) or "attachment"
    problem_id = _normalize_request_value(problem_id)
    volunteer_id = _normalize_request_value(volunteer_id)
    label = _normalize_request_value(label)

    asset_id = f"media-{uuid.uuid4().hex[:12]}"
    suffix = Path(file.filename or "").suffix
    if not suffix and file.content_type:
        guessed_suffix = mimetypes.guess_extension(file.content_type)
        suffix = guessed_suffix or ""
    suffix = suffix or ".bin"
    entity_key = problem_id or volunteer_id or "general"
    target_dir = MEDIA_ROOT / _safe_identifier(kind) / _safe_identifier(entity_key)
    target_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        payload = tmp_path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        final_name = f"{asset_id}{suffix}"
        final_path = target_dir / final_name
        shutil.move(str(tmp_path), final_path)
        asset = {
            "id": asset_id,
            "kind": kind,
            "problem_id": problem_id,
            "volunteer_id": volunteer_id,
            "label": label,
            "filename": file.filename,
            "stored_filename": final_name,
            "mime_type": file.content_type,
            "size_bytes": len(payload),
            "sha256": digest,
            "path": str(final_path.resolve()),
            "url": _media_relative_url(final_path),
            "created_at": _now_iso(),
        }
        MEDIA_ASSETS.append(asset)
        if problem_id:
            problem = next((item for item in PROBLEMS if item.get("id") == problem_id), None)
            if problem:
                _attach_media_to_problem(problem, asset)
        return asset
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


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
    profiles: Dict[str, Dict[str, Any]] = {}
    try:
        for row in DATA_STORE.load_seed_rows("runtime_profiles"):
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
        if profiles:
            return profiles
    except Exception:
        pass

    if not os.path.exists(RUNTIME_PROFILES_CSV):
        return {}
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


def _normalize_availability(volunteer: Dict[str, Any]) -> str:
    value = (
        volunteer.get("availability")
        or volunteer.get("availability_status")
        or "available"
    )
    return str(value).strip().lower() or "available"


def _runtime_people_rows() -> List[Dict[str, Any]]:
    try:
        return DATA_STORE.get_people_rows()
    except Exception:
        canonical_rows = read_csv_norm(DEFAULT_PEOPLE_CSV)
        canonical_by_id: Dict[str, Dict[str, Any]] = {}
        for row in canonical_rows:
            volunteer_id = get_any(row, ["person_id", "student_id", "id"])
            if volunteer_id:
                canonical_by_id[str(volunteer_id)] = dict(row)

        rows: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        for volunteer in VOLUNTEERS:
            volunteer_id = str(volunteer.get("id") or volunteer.get("user_id") or "")
            if not volunteer_id:
                continue
            source = dict(canonical_by_id.get(volunteer_id, {}))
            profile = volunteer.get("profiles") or {}
            skills = [str(skill).strip() for skill in volunteer.get("skills", []) if str(skill).strip()]
            skills_text = ";".join(skills)
            row = {
                **source,
                "person_id": volunteer_id,
                "id": volunteer_id,
                "user_id": volunteer.get("user_id") or volunteer_id,
                "name": profile.get("full_name") or source.get("name") or volunteer_id,
                "full_name": profile.get("full_name") or source.get("full_name") or volunteer_id,
                "email": profile.get("email") or source.get("email"),
                "phone": profile.get("phone") or source.get("phone"),
                "skills": skills_text,
                "text": skills_text,
                "availability": _normalize_availability(volunteer),
                "availability_status": volunteer.get("availability_status") or source.get("availability_status") or "available",
                "home_location": volunteer.get("home_location") or source.get("home_location") or source.get("village") or "",
            }
            if "willingness_eff" not in row:
                row["willingness_eff"] = source.get("willingness_eff", 0.5)
            if "willingness_bias" not in row:
                row["willingness_bias"] = source.get("willingness_bias", 0.5)
            rows.append(row)
            seen_ids.add(volunteer_id)

        for volunteer_id, row in canonical_by_id.items():
            if volunteer_id in seen_ids:
                continue
            rows.append(dict(row))

        return rows


def _sync_runtime_people_csv() -> str:
    rows = _runtime_people_rows()
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    if not fieldnames:
        fieldnames = [
            "person_id",
            "id",
            "user_id",
            "name",
            "full_name",
            "skills",
            "text",
            "availability",
            "availability_status",
            "home_location",
            "willingness_eff",
            "willingness_bias",
        ]

    with open(RUNTIME_PEOPLE_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    return RUNTIME_PEOPLE_CSV


def _volunteer_lookup_by_candidate_id(candidate_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not candidate_id:
        return None
    target = str(candidate_id)
    for volunteer in VOLUNTEERS:
        if (
            str(volunteer.get("id")) == target
            or str(volunteer.get("user_id")) == target
        ):
            return volunteer
    return None


def _build_problem_match(problem: Dict[str, Any], volunteer: Dict[str, Any], rank: int, source_note: str) -> Dict[str, Any]:
    volunteer_id = volunteer.get("id") or volunteer.get("user_id")
    return {
        "id": f"match-{problem['id']}-{rank + 1}-{int(datetime.now().timestamp())}",
        "problem_id": problem["id"],
        "volunteer_id": volunteer_id,
        "assigned_at": _now_iso(),
        "completed_at": None,
        "notes": source_note,
        "volunteers": volunteer,
    }


def _recommendation_payload_for_problem(problem: Dict[str, Any], *, people_csv: str) -> Dict[str, Any]:
    existing_team_size = len(problem.get("matches") or [])
    team_size = min(max(existing_team_size or 2, 1), 4)
    task_start = datetime.now()
    task_end = task_start + timedelta(hours=4)
    return {
        "proposal_text": problem.get("description") or problem.get("title") or "Village issue",
        "village_name": problem.get("village_name"),
        "task_start": task_start.isoformat(),
        "task_end": task_end.isoformat(),
        "team_size": team_size,
        "num_teams": 1,
        "auto_extract": True,
        "transcription": problem.get("transcript"),
        "visual_tags": list(problem.get("visual_tags") or []),
        "people_csv": people_csv,
        "people_rows": _runtime_people_rows(),
        "use_database": True,
        "model_path": DEFAULT_MODEL_PATH,
    }


def _tokenize_text(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _problem_relevance_score(problem: Dict[str, Any], volunteer: Dict[str, Any]) -> int:
    skills = [str(skill).strip().lower() for skill in volunteer.get("skills", []) if str(skill).strip()]
    skill_tokens = {token for skill in skills for token in _tokenize_text(skill)}
    problem_text = " ".join(
        str(part or "")
        for part in [
            problem.get("title"),
            problem.get("description"),
            problem.get("category"),
            " ".join(problem.get("visual_tags") or []),
            problem.get("transcript"),
        ]
    ).lower()
    problem_tokens = _tokenize_text(problem_text)
    overlap = skill_tokens & problem_tokens
    return len(overlap)


def _personalized_reassign_for_volunteer(volunteer: Dict[str, Any], reason: str) -> int:
    open_problems = [problem for problem in PROBLEMS if problem.get("status") != "completed"]
    if not open_problems:
        return 0

    volunteer_id = volunteer.get("id") or volunteer.get("user_id")
    personalized_rows = [row for row in _runtime_people_rows() if str(row.get("person_id")) == str(volunteer.get("id"))]
    if not personalized_rows:
        return 0

    scored_candidates: List[tuple[float, int, Dict[str, Any]]] = []
    for problem in open_problems:
        payload = _recommendation_payload_for_problem(problem, people_csv="")
        payload["team_size"] = 1
        payload["num_teams"] = 1
        payload["people_rows"] = personalized_rows
        payload["use_database"] = True
        try:
            results = recommender_service.generate_recommendations(payload)
        except Exception as exc:
            logger.warning("Failed to score problem %s for volunteer %s: %s", problem.get("id"), volunteer_id, exc)
            continue
        top_team = (results.get("teams") or [{}])[0]
        score = float(top_team.get("goodness") or 0.0)
        lexical = _problem_relevance_score(problem, volunteer)
        scored_candidates.append((score, lexical, problem))

    scored_candidates.sort(key=lambda item: (item[0], item[1], str(item[2].get("created_at") or "")), reverse=True)
    selected_problem_ids = {problem["id"] for score, lexical, problem in scored_candidates[:3] if score > 0 or lexical > 0}
    if not selected_problem_ids and scored_candidates:
        selected_problem_ids.add(scored_candidates[0][2]["id"])

    reassigned = 0
    for problem in open_problems:
        original_matches = list(problem.get("matches") or [])
        retained_matches = [match for match in original_matches if not _match_targets_volunteer(match, str(volunteer_id))]
        if problem["id"] in selected_problem_ids:
            retained_matches.insert(0, _build_problem_match(problem, volunteer, 0, f"Auto-rematched after {reason}"))
            problem["status"] = "in_progress"
            reassigned += 1
        else:
            problem["status"] = "in_progress" if retained_matches else "pending"
        if retained_matches != original_matches:
            problem["matches"] = retained_matches
            problem["updated_at"] = _now_iso()

    return reassigned


def _rematch_open_problems(reason: str) -> int:
    people_rows = _runtime_people_rows()
    reassigned = 0

    for problem in PROBLEMS:
        if problem.get("status") == "completed":
            continue

        payload = _recommendation_payload_for_problem(problem, people_csv="")
        payload["people_rows"] = people_rows
        payload["use_database"] = True
        try:
            results = recommender_service.generate_recommendations(payload)
        except Exception as exc:
            logger.warning("Failed to recompute matches for %s: %s", problem.get("id"), exc)
            continue

        team = (results.get("teams") or [{}])[0]
        members = list(team.get("members") or [])
        new_matches: List[Dict[str, Any]] = []

        for rank, member in enumerate(members):
            volunteer = _volunteer_lookup_by_candidate_id(member.get("person_id") or member.get("id"))
            if not volunteer:
                continue
            new_matches.append(
                _build_problem_match(problem, volunteer, rank, f"Auto-rematched after {reason}")
            )

        problem["matches"] = new_matches
        problem["updated_at"] = _now_iso()
        problem["status"] = "in_progress" if new_matches else "pending"
        reassigned += 1

    return reassigned


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
    problems: List[Dict[str, Any]] = []
    for index, row in enumerate(read_csv_norm(DEFAULT_PROPOSALS_CSV)):
        problem_id = get_any(row, ["proposal_id", "id"])
        if not problem_id:
            continue
        status = get_any(row, ["status"], "pending")
        created_at = _seed_timestamp(index)
        village_name = get_any(row, ["village", "village_name"], "Unknown")
        lat, lng = _village_coordinates(village_name)
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


def _build_seed_profiles(
    profile_directory: Dict[str, Dict[str, Any]],
    volunteers: List[Dict[str, Any]],
    problems: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = dict(profile_directory)
    for volunteer in volunteers:
        profile = volunteer.get("profiles")
        if profile and profile.get("id"):
            profiles[str(profile["id"])] = profile
    for problem in problems:
        profile = problem.get("profiles")
        if profile and profile.get("id"):
            profiles[str(profile["id"])] = profile
    return list(profiles.values())


def persist_runtime_state() -> None:
    global STATE_VERSION
    with csv_lock:
        db_error: Optional[Exception] = None
        try:
            DATA_STORE.save_runtime_state(
                problems=PROBLEMS,
                volunteers=VOLUNTEERS,
                profiles=PROFILES,
                media_assets=MEDIA_ASSETS,
            )
        except Exception as exc:
            db_error = exc
            logger.warning("Failed to persist runtime state to Postgres: %s", exc)
        STATE_VERSION += 1
        try:
            if db_error is None:
                DATA_STORE.set_meta("state_version", STATE_VERSION)
        except Exception as exc:
            logger.warning("Failed to persist state version metadata: %s", exc)
        try:
            runtime_snapshot = {
                "state_version": STATE_VERSION,
                "problems": PROBLEMS,
                "volunteers": VOLUNTEERS,
                "profiles": PROFILES,
                "media_assets": MEDIA_ASSETS,
            }
            Path(RUNTIME_STATE_JSON).parent.mkdir(parents=True, exist_ok=True)
            with open(RUNTIME_STATE_JSON, "w", encoding="utf-8") as handle:
                json.dump(runtime_snapshot, handle, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:
            logger.warning("Failed to export runtime state snapshot: %s", exc)
        try:
            _sync_runtime_people_csv()
        except Exception as exc:
            logger.warning("Failed to export live people CSV: %s", exc)


def _match_targets_volunteer(match: Dict[str, Any], volunteer_id: str) -> bool:
    volunteer = match.get("volunteers", {})
    return (
        match.get("volunteer_id") == volunteer_id
        or volunteer.get("user_id") == volunteer_id
        or volunteer.get("id") == volunteer_id
    )


def _attach_duplicate_report(
    target_problem: Dict[str, Any],
    *,
    request: ProblemRequest,
    duplicate_score: float,
    duplicate_reason: str,
    matched_problem_id: str,
) -> Dict[str, Any]:
    duplicate_report = {
        "id": f"dup-{uuid.uuid4().hex[:12]}",
        "problem_id": matched_problem_id,
        "reported_at": _now_iso(),
        "reporter_name": request.reporter_name,
        "reporter_phone": request.reporter_phone,
        "reporter_id": request.villager_id or request.coordinator_id,
        "title": request.title,
        "description": request.description,
        "category": request.category,
        "village_name": request.village_name,
        "village_address": request.village_address,
        "severity": request.severity,
        "visual_tags": list(request.visual_tags or []),
        "transcript": request.transcript,
        "transcript_language": request.transcript_language,
        "source": "auto-duplicate-merge",
        "duplicate_score": round(float(duplicate_score), 3),
        "duplicate_reason": duplicate_reason,
    }
    reports = target_problem.setdefault("duplicate_reports", [])
    if not isinstance(reports, list):
        reports = []
        target_problem["duplicate_reports"] = reports
    reports.append(duplicate_report)
    target_problem["duplicate_count"] = len(reports)
    target_problem["updated_at"] = _now_iso()
    return duplicate_report


def _problem_timeline(problem: Dict[str, Any]) -> Dict[str, Any]:
    timeline: List[Dict[str, Any]] = []
    problem_id = str(problem.get("id") or "")

    created_at = problem.get("created_at") or problem.get("updated_at") or _now_iso()
    timeline.append({
        "type": "reported",
        "timestamp": created_at,
        "title": "Problem reported",
        "summary": problem.get("title") or "Problem reported",
        "details": problem.get("description") or "",
        "source": "problem",
    })

    for duplicate in problem.get("duplicate_reports") or []:
        timeline.append({
            "type": "duplicate_reported",
            "timestamp": duplicate.get("reported_at") or created_at,
            "title": "Duplicate report attached",
            "summary": duplicate.get("title") or "Repeated complaint",
            "details": duplicate.get("duplicate_reason") or "Attached as a duplicate report.",
            "source": "duplicate",
            "data": duplicate,
        })

    for asset in MEDIA_ASSETS:
        if asset.get("problem_id") != problem_id:
            continue
        timeline.append({
            "type": "media_uploaded",
            "timestamp": asset.get("created_at") or created_at,
            "title": f"Media uploaded: {asset.get('kind') or 'attachment'}",
            "summary": asset.get("label") or asset.get("filename") or asset.get("kind") or "Uploaded media",
            "details": asset.get("url") or "",
            "source": "media",
            "data": {
                "media_id": asset.get("id"),
                "kind": asset.get("kind"),
                "label": asset.get("label"),
                "url": asset.get("url"),
            },
        })

    for match in problem.get("matches") or []:
        volunteer = match.get("volunteers") or {}
        volunteer_name = (
            volunteer.get("profiles", {}).get("full_name")
            or volunteer.get("profile", {}).get("full_name")
            or volunteer.get("name")
            or volunteer.get("id")
            or volunteer.get("user_id")
            or "Volunteer"
        )
        timeline.append({
            "type": "assigned",
            "timestamp": match.get("assigned_at") or created_at,
            "title": "Volunteer assigned",
            "summary": volunteer_name,
            "details": match.get("notes") or "",
            "source": "assignment",
            "data": {
                "match_id": match.get("id"),
                "volunteer_id": match.get("volunteer_id"),
            },
        })
        if match.get("completed_at"):
            timeline.append({
                "type": "completed",
                "timestamp": match.get("completed_at") or created_at,
                "title": "Match completed",
                "summary": volunteer_name,
                "details": match.get("notes") or "Volunteer marked the case as complete.",
                "source": "assignment",
                "data": {
                    "match_id": match.get("id"),
                    "volunteer_id": match.get("volunteer_id"),
                },
            })

    try:
        events = DATA_STORE.get_recent_learning_events(
            limit=200,
            entity_type="problem",
            entity_id=problem_id,
        )
        for event in events:
            timeline.append({
                "type": event.get("event_type"),
                "timestamp": event.get("created_at"),
                "title": event.get("summary") or event.get("event_type"),
                "summary": event.get("summary") or event.get("event_type"),
                "details": json.dumps(event.get("data") or {}, ensure_ascii=False),
                "source": "learning_event",
                "data": event.get("data") or {},
            })
    except Exception as exc:
        logger.warning("Failed to load learning events for timeline %s: %s", problem_id, exc)

    timeline.sort(key=lambda item: str(item.get("timestamp") or ""))
    return {
        "problem_id": problem_id,
        "problem": _serialize_problem(problem),
        "timeline": timeline,
        "summary": {
            "event_count": len(timeline),
            "media_count": sum(1 for item in timeline if item["type"] == "media_uploaded"),
            "assignment_count": sum(1 for item in timeline if item["type"] == "assigned"),
            "duplicate_count": len(problem.get("duplicate_reports") or []),
            "completed": problem.get("status") == "completed",
        },
    }


def _public_status_board(
    problems: List[Dict[str, Any]],
    *,
    village_name: Optional[str] = None,
    status_filter: Optional[str] = None,
    days_back: int = 60,
) -> Dict[str, Any]:
    cutoff = datetime.now() - timedelta(days=max(1, days_back))
    filtered: List[Dict[str, Any]] = []
    for problem in problems:
        created_at_raw = problem.get("created_at") or problem.get("updated_at")
        created_at = None
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
                if created_at.tzinfo:
                    created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                created_at = None
        if created_at and created_at < cutoff:
            continue
        if village_name and str(problem.get("village_name") or "").strip().lower() != village_name.strip().lower():
            continue
        if status_filter and str(problem.get("status") or "") != status_filter:
            continue
        filtered.append(problem)

    items: List[Dict[str, Any]] = []
    for problem in sorted(filtered, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True):
        items.append({
            "id": str(problem.get("id") or ""),
            "title": problem.get("title") or "Untitled problem",
            "category": problem.get("category"),
            "village_name": problem.get("village_name"),
            "village_address": problem.get("village_address"),
            "status": problem.get("status") or "pending",
            "severity": problem.get("severity"),
            "created_at": problem.get("created_at"),
            "updated_at": problem.get("updated_at"),
            "assigned_count": len(problem.get("matches") or []),
            "duplicate_count": len(problem.get("duplicate_reports") or []),
            "media_count": len(problem.get("media_ids") or []),
        })

    open_count = sum(1 for problem in filtered if problem.get("status") == "pending")
    in_progress_count = sum(1 for problem in filtered if problem.get("status") == "in_progress")
    completed_count = sum(1 for problem in filtered if problem.get("status") == "completed")
    return {
        "generated_at": _now_iso(),
        "window_days": days_back,
        "village_name": village_name,
        "status_filter": status_filter,
        "open_count": open_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
        "total_count": len(filtered),
        "items": items[:100],
    }


def _problem_topic(problem: Dict[str, Any]) -> str:
    triage = infer_problem_triage(
        problem_title=str(problem.get("title") or ""),
        problem_description=str(problem.get("description") or ""),
        category=problem.get("category"),
        visual_tags=list(problem.get("visual_tags") or []),
        severity=problem.get("severity"),
    )
    return str(triage.get("topic") or "general")


def _problem_playbook(problem: Dict[str, Any], proof: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    topic = _problem_topic(problem)
    steps = [
        f"Inspect the {problem.get('category') or topic} issue reported in {problem.get('village_name') or 'the village'}.",
        "Secure the area and verify that the issue is safe to approach.",
        "Apply the smallest safe temporary fix that keeps the service usable.",
        "Document what was changed with before/after photos and notes.",
    ]
    materials = sorted({
        *(problem.get("visual_tags") or []),
        problem.get("category") or "",
        topic,
    })
    materials = [item for item in materials if item]
    safety_notes = [
        "Do not attempt a repair if the situation is electrically live, pressurized, or structurally unstable.",
        "Stop if the temporary fix starts failing or creates a new hazard.",
    ]
    summary = (
        proof.get("notes")
        if proof and proof.get("notes")
        else problem.get("description")
        or "Solved case playbook derived from the completed issue."
    )
    return {
        "id": f"playbook-{problem.get('id')}",
        "topic": topic,
        "village_name": problem.get("village_name"),
        "title": problem.get("title") or "Solved case playbook",
        "summary": summary,
        "materials": materials,
        "safety_notes": safety_notes,
        "steps": steps,
        "source_problem_id": problem.get("id"),
        "source_problem_title": problem.get("title"),
        "created_at": _now_iso(),
    }


def _record_playbook_for_problem(problem: Dict[str, Any], proof: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    playbook = _problem_playbook(problem, proof)
    try:
        DATA_STORE.save_playbook(
            playbook_id=playbook["id"],
            topic=playbook["topic"],
            village_name=playbook.get("village_name"),
            data=playbook,
        )
    except Exception as exc:
        logger.warning("Failed to persist playbook for %s: %s", problem.get("id"), exc)
    return playbook


def _escalation_level(problem: Dict[str, Any]) -> Dict[str, Any]:
    created_at_raw = problem.get("created_at") or problem.get("updated_at")
    created_at = None
    if created_at_raw:
        try:
            created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
            if created_at.tzinfo:
                created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            created_at = None
    age_hours = max(0.0, (datetime.now() - created_at).total_seconds() / 3600.0) if created_at else 0.0
    severity = str(problem.get("severity") or "NORMAL").upper()
    thresholds = {
        "HIGH": (12, 48, 96),
        "NORMAL": (24, 72, 168),
        "LOW": (48, 120, 240),
    }
    coordinator, supervisor, partner = thresholds.get(severity, thresholds["NORMAL"])
    if age_hours >= partner:
        level = "partner_org"
    elif age_hours >= supervisor:
        level = "supervisor"
    elif age_hours >= coordinator:
        level = "coordinator"
    else:
        level = "watch"
    return {
        "problem_id": problem.get("id"),
        "title": problem.get("title"),
        "village_name": problem.get("village_name"),
        "severity": severity,
        "status": problem.get("status"),
        "age_hours": round(age_hours, 1),
        "escalation_level": level,
        "next_action": {
            "coordinator": "Notify the coordinator immediately.",
            "supervisor": "Escalate to the supervisor and request a review.",
            "partner_org": "Escalate outside the village chain to the partner org.",
            "watch": "Continue monitoring for movement.",
        }.get(level, "Continue monitoring for movement."),
    }


def _volunteer_reputation(problems: List[Dict[str, Any]], volunteers: List[Dict[str, Any]], days_back: int = 90) -> List[Dict[str, Any]]:
    cutoff = datetime.now() - timedelta(days=max(1, days_back))
    rows: List[Dict[str, Any]] = []
    for volunteer in volunteers:
        volunteer_id = str(volunteer.get("id") or volunteer.get("user_id") or "")
        if not volunteer_id:
            continue
        completed = 0
        open_assignments = 0
        duplicate_reports = 0
        resolution_hours: List[float] = []
        for problem in problems:
            problem_created_raw = problem.get("created_at") or problem.get("updated_at")
            problem_created = None
            if problem_created_raw:
                try:
                    problem_created = datetime.fromisoformat(str(problem_created_raw).replace("Z", "+00:00"))
                    if problem_created.tzinfo:
                        problem_created = problem_created.astimezone(timezone.utc).replace(tzinfo=None)
                except ValueError:
                    problem_created = None
            if problem_created and problem_created < cutoff:
                continue

            duplicate_reports += len(problem.get("duplicate_reports") or [])
            for match in problem.get("matches") or []:
                if not _match_targets_volunteer(match, volunteer_id):
                    continue
                assigned_at = match.get("assigned_at")
                completed_at = match.get("completed_at")
                assigned_dt = None
                completed_dt = None
                try:
                    assigned_dt = datetime.fromisoformat(str(assigned_at).replace("Z", "+00:00")) if assigned_at else None
                    if assigned_dt and assigned_dt.tzinfo:
                        assigned_dt = assigned_dt.astimezone(timezone.utc).replace(tzinfo=None)
                except ValueError:
                    assigned_dt = None
                try:
                    completed_dt = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00")) if completed_at else None
                    if completed_dt and completed_dt.tzinfo:
                        completed_dt = completed_dt.astimezone(timezone.utc).replace(tzinfo=None)
                except ValueError:
                    completed_dt = None
                if assigned_dt and assigned_dt < cutoff:
                    open_assignments += 1 if not completed_dt else 0
                if completed_dt:
                    completed += 1
                    if assigned_dt:
                        resolution_hours.append(max(0.0, (completed_dt - assigned_dt).total_seconds() / 3600.0))

        avg_hours = sum(resolution_hours) / len(resolution_hours) if resolution_hours else None
        reliability = 0.5
        if completed:
            reliability += min(0.3, completed * 0.03)
        if avg_hours is not None:
            reliability += max(0.0, 0.2 - min(avg_hours / 72.0, 0.2))
        reliability -= min(0.3, open_assignments * 0.05)
        reliability = max(0.0, min(1.0, reliability))
        rows.append({
            "volunteer_id": volunteer_id,
            "name": str((volunteer.get("profiles") or {}).get("full_name") or volunteer.get("full_name") or volunteer_id),
            "home_location": volunteer.get("home_location") or "",
            "skills": list(volunteer.get("skills") or []),
            "completed_count": completed,
            "open_assignments": open_assignments,
            "duplicate_reports_seen": duplicate_reports,
            "avg_resolution_hours": round(avg_hours, 1) if avg_hours is not None else None,
            "reliability_score": round(reliability, 3),
        })
    rows.sort(key=lambda row: (row["reliability_score"], row["completed_count"]), reverse=True)
    return rows


def _route_optimizer(problems: List[Dict[str, Any]], volunteers: List[Dict[str, Any]], days_back: int = 14) -> List[Dict[str, Any]]:
    cutoff = datetime.now() - timedelta(days=max(1, days_back))
    eligible_problems: List[Dict[str, Any]] = []
    for problem in problems:
        if problem.get("status") == "completed":
            continue
        created_raw = problem.get("created_at") or problem.get("updated_at")
        if not created_raw:
            continue
        try:
            created_dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
            if created_dt.tzinfo:
                created_dt = created_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
        if created_dt >= cutoff:
            eligible_problems.append(problem)

    indexed = _serialize_problems(eligible_problems)
    if not indexed:
        return []

    routes_by_village: Dict[str, Dict[str, Any]] = {}
    volunteer_by_village: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for volunteer in volunteers:
        home = str(volunteer.get("home_location") or "").strip()
        if home:
            volunteer_by_village[home].append(volunteer)

    for problem in indexed:
        village = problem.get("village_name") or "Unknown"
        route = routes_by_village.setdefault(village, {
            "route_id": f"route-{len(routes_by_village) + 1}",
            "village_name": village,
            "problem_ids": [],
            "titles": [],
            "severity_counts": Counter(),
            "recommended_volunteers": [],
            "route_hint": "Cluster this village's open cases into one visit where possible.",
        })
        route["problem_ids"].append(problem.get("id"))
        route["titles"].append(problem.get("title"))
        route["severity_counts"][str(problem.get("severity") or "NORMAL")] += 1

    routes: List[Dict[str, Any]] = []
    for village, route in routes_by_village.items():
        volunteers_for_village = volunteer_by_village.get(village, [])
        routes.append({
            "route_id": route["route_id"],
            "village_name": village,
            "problem_ids": route["problem_ids"],
            "titles": route["titles"][:5],
            "problem_count": len(route["problem_ids"]),
            "severity_counts": dict(route["severity_counts"]),
            "recommended_volunteers": [
                {
                    "volunteer_id": str(volunteer.get("id") or volunteer.get("user_id")),
                    "name": (volunteer.get("profiles") or {}).get("full_name") or volunteer.get("full_name") or volunteer.get("id"),
                    "skills": list(volunteer.get("skills") or []),
                }
                for volunteer in volunteers_for_village[:3]
            ],
            "route_hint": route["route_hint"],
        })

    routes.sort(key=lambda item: (item["problem_count"], item["village_name"]), reverse=True)
    return routes


def _record_learning_event(
    event_type: str,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    summary: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    text: Optional[str] = None,
) -> None:
    try:
        DATA_STORE.record_learning_event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            payload=payload,
            text=text,
        )
    except Exception as exc:
        logger.warning("Failed to record learning event %s/%s: %s", event_type, entity_id, exc)


def load_initial_data(force_seed: bool = False):
    """Loads seeded runtime state backed by canonical CSV data."""
    global PROBLEMS, VOLUNTEERS, PROFILES, MEDIA_ASSETS, STATE_VERSION

    try:
        DATA_STORE.ensure_schema()
        DATA_STORE.ensure_seed_catalog(force=force_seed)
        if not force_seed:
            state_version = DATA_STORE.get_meta("state_version", None)
            if isinstance(state_version, int):
                STATE_VERSION = state_version
            elif isinstance(state_version, str):
                try:
                    STATE_VERSION = int(state_version)
                except ValueError:
                    STATE_VERSION = max(STATE_VERSION, 0)
            elif isinstance(state_version, dict) and "value" in state_version:
                try:
                    STATE_VERSION = int(state_version["value"])
                except (TypeError, ValueError):
                    STATE_VERSION = max(STATE_VERSION, 0)
    except Exception as exc:
        logger.warning("Failed to initialize Postgres catalog, falling back to CSV seed data: %s", exc)

    if not force_seed:
        try:
            runtime_state = DATA_STORE.load_runtime_state()
            if runtime_state.problems or runtime_state.volunteers or runtime_state.profiles or runtime_state.media_assets:
                PROBLEMS = list(runtime_state.problems)
                VOLUNTEERS = list(runtime_state.volunteers)
                PROFILES = list(runtime_state.profiles)
                MEDIA_ASSETS = list(runtime_state.media_assets)
                VILLAGE_COORDS_CACHE.clear()
                VILLAGE_COORDS_CACHE.update(DATA_STORE.get_village_coordinates())
                STATE_VERSION = max(STATE_VERSION, 1)
                return
        except Exception as exc:
            logger.warning("Failed to load runtime state from Postgres, rebuilding from canonical dataset: %s", exc)

    try:
        profile_directory = _load_profile_directory()
        VOLUNTEERS = _build_seed_volunteers(profile_directory)
        volunteers_by_id = {volunteer["id"]: volunteer for volunteer in VOLUNTEERS}
        PROBLEMS = _build_seed_problems(profile_directory, volunteers_by_id)
        PROFILES = _build_seed_profiles(profile_directory, VOLUNTEERS, PROBLEMS)
        MEDIA_ASSETS = []
        STATE_VERSION = 0
        persist_runtime_state()
        VILLAGE_COORDS_CACHE.clear()
        VILLAGE_COORDS_CACHE.update(DATA_STORE.get_village_coordinates())
    except Exception as exc:
        logger.error("Failed to load canonical seed data: %s", exc)
        PROBLEMS = []
        VOLUNTEERS = []
        PROFILES = []
        MEDIA_ASSETS = []
        STATE_VERSION = 0


def reset_runtime_state() -> None:
    global STATE_VERSION
    try:
        DATA_STORE.clear_runtime_state()
        DATA_STORE.set_meta("state_version", 0)
    except Exception as exc:
        logger.warning("Failed to clear Postgres runtime state: %s", exc)
    if os.path.exists(RUNTIME_PEOPLE_CSV):
        os.remove(RUNTIME_PEOPLE_CSV)
    if os.path.exists(RUNTIME_STATE_JSON):
        os.remove(RUNTIME_STATE_JSON)
    if os.path.exists(MEDIA_ROOT):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    VILLAGE_COORDS_CACHE.clear()
    STATE_VERSION = 0
    load_initial_data(force_seed=True)

# Load data on module import so the app has a usable in-memory snapshot immediately.
load_initial_data()


def train_model(request: Optional[TrainRequest] = None) -> float:
    """Backward-compatible training hook.

    The Nexus engine does not require training, but older callers and tests still
    expect this hook to exist and return an AUC-like score.
    """
    return 0.0


@app.post("/train", response_model=TrainResponse)
def train_endpoint(request: Optional[TrainRequest] = None):
    """Backward-compatible training endpoint."""
    auc = train_model(request)
    return TrainResponse(status="ok", auc=auc, model_path=str(DEFAULT_MODEL_PATH))


@app.get("/problems")
async def get_problems():
    return _serialize_problems(PROBLEMS)


@app.get("/state-version")
async def get_state_version():
    try:
        version = DATA_STORE.get_meta("state_version", STATE_VERSION)
        if isinstance(version, int):
            return {"version": version}
        if isinstance(version, str):
            try:
                return {"version": int(version)}
            except ValueError:
                pass
    except Exception:
        pass
    return {"version": STATE_VERSION}

@app.get("/volunteers")
async def get_volunteers():
    return VOLUNTEERS


@app.get("/profiles")
async def get_profiles():
    return PROFILES

@app.get("/volunteer/{volunteer_id}")
async def get_volunteer(volunteer_id: str):
    for volunteer in VOLUNTEERS:
        if volunteer["user_id"] == volunteer_id or volunteer["id"] == volunteer_id:
            return volunteer

    raise HTTPException(status_code=404, detail="Volunteer profile not found")


@app.post("/profile")
async def upsert_profile(data: ProfileRequest):
    profile = _upsert_profile(data.model_dump())
    if profile.get("role") == "villager":
        persist_runtime_state()
    else:
        persist_runtime_state()
    return {"status": "success", "profile": profile}

@app.post("/volunteer")
async def update_volunteer(data: Dict[str, Any]):
    logger.info(f"Volunteer profile updated for {data.get('user_id')}")
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    timestamp = _now_iso()
    updated_record: Optional[Dict[str, Any]] = None
    for volunteer in VOLUNTEERS:
        if volunteer.get("user_id") == user_id:
            volunteer.update(data)
            volunteer.setdefault("id", data.get("id") or f"vol-{user_id}")
            volunteer.setdefault("created_at", timestamp)
            volunteer["updated_at"] = timestamp
            volunteer["availability"] = data.get("availability") or data.get("availability_status") or volunteer.get("availability") or "available"
            volunteer["profiles"] = _upsert_profile(data.get("profiles") or {
                "id": user_id,
                "full_name": data.get("full_name") or volunteer.get("profiles", {}).get("full_name") or "Volunteer",
                "email": data.get("email") or volunteer.get("profiles", {}).get("email"),
                "phone": data.get("phone") or volunteer.get("profiles", {}).get("phone"),
                "role": "volunteer",
                "created_at": volunteer.get("profiles", {}).get("created_at") or timestamp,
            })
            updated_record = volunteer
            break

    if updated_record is None:
        new_volunteer = {
            "id": data.get("id") or f"vol-{user_id}",
            "user_id": user_id,
            "skills": list(data.get("skills") or []),
            "availability_status": data.get("availability_status") or "available",
            "availability": data.get("availability") or data.get("availability_status") or "available",
            "home_location": data.get("home_location") or "",
            "created_at": timestamp,
            "updated_at": timestamp,
            "profiles": _upsert_profile(data.get("profiles") or {
                "id": user_id,
                "full_name": data.get("full_name") or "Volunteer",
                "email": data.get("email"),
                "phone": data.get("phone"),
                "role": "volunteer",
                "created_at": timestamp,
            }),
        }
        VOLUNTEERS.append(new_volunteer)
        updated_record = new_volunteer

    rematched = _rematch_open_problems(f"volunteer profile update for {user_id}")
    personalized = _personalized_reassign_for_volunteer(updated_record, f"volunteer profile update for {user_id}")
    _record_learning_event(
        "volunteer_updated",
        entity_type="volunteer",
        entity_id=str(updated_record.get("id") or user_id),
        summary=f"Volunteer profile updated for {user_id}",
        payload={"volunteer": updated_record, "rematched_problems": rematched, "personalized_tasks": personalized},
        text=" ".join([
            str(updated_record.get("id") or ""),
            str(updated_record.get("skills") or ""),
            str(updated_record.get("availability") or ""),
            str(updated_record.get("home_location") or ""),
        ]),
    )
    persist_runtime_state()
    logger.info(
        "Recomputed assignments for %s open problems after volunteer update and personalized %s tasks for %s.",
        rematched,
        personalized,
        user_id,
    )
    return {
        "status": "success",
        "data": updated_record,
        "rematched_problems": rematched,
        "personalized_tasks": personalized,
    }

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
                "category": problem.get("category", "others"),
                "severity": problem.get("severity", "NORMAL"),
                "severity_source": problem.get("severity_source", "Auto-detected"),
                "assigned_at": assigned_at,
                "media_assets": [asset for asset in (_asset_by_id(media_id) for media_id in problem.get("media_ids", [])) if asset],
                "proof": problem.get("proof"),
                "proof_assets": [asset for asset in (_asset_by_id(media_id) for media_id in problem.get("proof", {}).get("media_ids", [])) if asset],
            }
    # Sort: HIGH severity first, then NORMAL, then LOW; within same severity by assigned_at desc
    severity_order = {"HIGH": 0, "NORMAL": 1, "LOW": 2}
    return sorted(
        tasks_by_problem.values(),
        key=lambda t: (severity_order.get(t.get("severity", "NORMAL"), 1), t["assigned_at"]),
    )

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
    _record_learning_event(
        "task_assigned",
        entity_type="problem",
        entity_id=problem_id,
        summary=f"Assigned {volunteer_id} to {problem_id}",
        payload={"problem_id": problem_id, "volunteer_id": volunteer_id, "match": match},
        text=" ".join([
            problem.get("title", ""),
            problem.get("description", ""),
            str(volunteer.get("skills") or ""),
            problem.get("village_name", ""),
        ]),
    )
    persist_runtime_state()
    notify_team_assignment(
        [{"members": [volunteer]}],
        problem.get("title", "Reported issue"),
        problem.get("village_name", "Village"),
    )

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
    _record_learning_event(
        "problem_status_changed",
        entity_type="problem",
        entity_id=problem_id,
        summary=f"Problem {problem_id} changed to {new_status}",
        payload={"problem_id": problem_id, "status": new_status},
        text=" ".join([
            problem.get("title", ""),
            problem.get("description", ""),
            new_status,
            problem.get("category", ""),
            problem.get("village_name", ""),
        ]),
    )
    if new_status == "completed":
        completed_at = _now_iso()
        for match in problem.get("matches", []):
            match["completed_at"] = match.get("completed_at") or completed_at
        villager_phone = (
            problem.get("profiles", {}).get("phone")
            or problem.get("profile", {}).get("phone")
        )
        notify_problem_resolved(villager_phone, problem.get("title", "Reported issue"))
        notify_problem_follow_up(villager_phone, problem.get("title", "Reported issue"))
        _record_playbook_for_problem(problem)
    elif new_status in {"pending", "in_progress"}:
        for match in problem.get("matches", []):
            match["completed_at"] = None
    persist_runtime_state()
    return {"status": "success", "problem": _serialize_problem(problem)}


@app.delete("/problems/{problem_id}")
async def delete_problem(problem_id: str):
    global PROBLEMS
    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    PROBLEMS = [p for p in PROBLEMS if p["id"] != problem_id]
    _record_learning_event(
        "problem_deleted",
        entity_type="problem",
        entity_id=problem_id,
        summary=f"Deleted problem {problem_id}",
        payload={"problem": problem},
        text=" ".join([
            problem.get("title", ""),
            problem.get("description", ""),
            problem.get("category", ""),
            problem.get("village_name", ""),
        ]),
    )
    persist_runtime_state()
    return {"status": "success", "deleted_id": problem_id}


@app.patch("/problems/{problem_id}")
async def edit_problem(problem_id: str, payload: Dict[str, Any]):
    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    editable = {"title", "description", "category", "village_name", "village_address", "visual_tags"}
    for key in editable:
        if key in payload:
            problem[key] = payload[key]
    problem["updated_at"] = _now_iso()
    _record_learning_event(
        "problem_edited",
        entity_type="problem",
        entity_id=problem_id,
        summary=f"Edited problem {problem_id}",
        payload={"problem_id": problem_id, "changes": {key: payload[key] for key in editable if key in payload}},
        text=" ".join([
            problem.get("title", ""),
            problem.get("description", ""),
            problem.get("category", ""),
            problem.get("village_name", ""),
        ]),
    )
    persist_runtime_state()
    return {"status": "success", "problem": _serialize_problem(problem)}


@app.delete("/problems/{problem_id}/matches/{match_id}")
async def unassign_volunteer(problem_id: str, match_id: str):
    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    original = list(problem.get("matches") or [])
    problem["matches"] = [m for m in original if m.get("id") != match_id]
    if not problem["matches"] and problem["status"] == "in_progress":
        problem["status"] = "pending"
    problem["updated_at"] = _now_iso()
    _record_learning_event(
        "task_unassigned",
        entity_type="problem",
        entity_id=problem_id,
        summary=f"Removed match {match_id} from {problem_id}",
        payload={"problem_id": problem_id, "match_id": match_id},
        text=" ".join([
            problem.get("title", ""),
            problem.get("description", ""),
            problem.get("village_name", ""),
        ]),
    )
    persist_runtime_state()
    return {"status": "success", "problem": _serialize_problem(problem)}


@app.post("/media")
async def upload_media(
    file: UploadFile = File(...),
    kind: str = Form("attachment"),
    problem_id: Optional[str] = Form(None),
    volunteer_id: Optional[str] = Form(None),
    label: Optional[str] = Form(None),
):
    asset = _store_media_file(
        file,
        kind=kind,
        problem_id=problem_id,
        volunteer_id=volunteer_id,
        label=label,
    )
    _record_learning_event(
        "media_uploaded",
        entity_type="media",
        entity_id=asset.get("id"),
        summary=f"Uploaded {kind} media",
        payload={"asset": asset},
        text=" ".join([
            str(asset.get("kind") or ""),
            str(asset.get("label") or ""),
            str(asset.get("filename") or ""),
            str(asset.get("problem_id") or ""),
        ]),
    )
    persist_runtime_state()
    return {"status": "success", "media": asset}


@app.post("/problems/{problem_id}/proof")
async def submit_proof(problem_id: str, request: ProofRequest):
    problem = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    media_asset_ids = [media_id for media_id in [request.before_media_id, request.after_media_id] if media_id]
    if media_asset_ids:
        missing_assets = [media_id for media_id in media_asset_ids if not _asset_by_id(media_id)]
        if missing_assets:
            raise HTTPException(status_code=404, detail=f"Media asset(s) not found: {', '.join(missing_assets)}")

    verification = _verify_problem_proof(problem, request)
    proof = _attach_proof_to_problem(problem, media_asset_ids, request.volunteer_id, request.notes)
    proof["verification"] = verification
    _record_learning_event(
        "proof_submitted",
        entity_type="problem",
        entity_id=problem_id,
        summary=f"Proof submitted for {problem_id}",
        payload={"problem_id": problem_id, "proof": proof, "verification": verification},
        text=" ".join([
            problem.get("title", ""),
            problem.get("description", ""),
            str(request.notes or ""),
            str(verification.get("summary") or ""),
        ]),
    )
    _record_playbook_for_problem(problem, proof)
    persist_runtime_state()
    return {"status": "success", "problem": _serialize_problem(problem), "proof": proof}


@app.post("/api/v1/jugaad/assist", response_model=JugaadResponse)
async def jugaad_assist_endpoint(request: JugaadRequest):
    problem = next((p for p in PROBLEMS if p["id"] == request.problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    broken_asset = _asset_by_id(request.broken_media_id)
    materials_asset = _asset_by_id(request.materials_media_id)
    if not broken_asset:
        raise HTTPException(status_code=404, detail="Broken-part image not found")
    if not materials_asset:
        raise HTTPException(status_code=404, detail="Materials image not found")

    try:
        result = suggest_jugaad_fix(
            broken_asset.get("path"),
            materials_asset.get("path"),
            problem_title=problem.get("title", "Village issue"),
            problem_description=problem.get("description", ""),
            category=problem.get("category"),
            visual_tags=list(problem.get("visual_tags") or []),
            materials_note=request.notes,
        )
        _record_learning_event(
            "jugaad_assist_requested",
            entity_type="problem",
            entity_id=request.problem_id,
            summary=f"Jugaad guidance requested for {request.problem_id}",
            payload={"request": request.model_dump(), "result": result},
            text=" ".join([
                problem.get("title", ""),
                problem.get("description", ""),
                problem.get("category", ""),
                str(request.notes or ""),
            ]),
        )
        return JugaadResponse(problem_id=request.problem_id, **result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Jugaad guidance failed for %s", request.problem_id)
        raise HTTPException(status_code=500, detail=f"Jugaad guidance failed: {exc}")


@app.post("/api/v1/problems/instant-guidance", response_model=ProblemGuidanceResponse)
async def problem_guidance_endpoint(request: ProblemGuidanceRequest):
    try:
        triage = infer_problem_triage(
            problem_title=request.title,
            problem_description=request.description,
            category=request.category,
            visual_tags=request.visual_tags,
            severity=request.severity,
        )
        duplicate_candidates = find_duplicate_problem_candidates(
            PROBLEMS,
            title=request.title,
            description=request.description,
            village_name=request.village_name,
            category=request.category,
            visual_tags=request.visual_tags,
            transcript=request.transcript,
            limit=4,
        )
        guidance = suggest_immediate_problem_actions(
            problem_title=request.title,
            problem_description=request.description,
            category=request.category,
            visual_tags=request.visual_tags,
            severity=request.severity,
        )
        guidance_payload = dict(guidance)
        guidance_payload.pop("department", None)
        guidance_payload.pop("urgency", None)
        guidance_payload.pop("response_path", None)
        response = ProblemGuidanceResponse(
            **guidance_payload,
            department=triage["department"],
            urgency=triage["urgency"],
            response_path=triage["response_path"],
            duplicate_candidates=duplicate_candidates,
            similar_problem_count=len(duplicate_candidates),
            root_cause_hint=triage.get("root_cause_hint"),
        )
        _record_learning_event(
            "instant_guidance_requested",
            entity_type="problem",
            summary=f"Instant guidance requested for {request.title}",
            payload={"request": request.model_dump(), "response": response.model_dump()},
            text=" ".join([
                request.title,
                request.description,
                request.category or "",
                " ".join(request.visual_tags or []),
            ]),
        )
        return response
    except Exception as exc:
        logger.exception("Instant problem guidance failed")
        raise HTTPException(status_code=500, detail=f"Instant guidance failed: {exc}")


@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(request: RecommendRequest):
    try:
        payload = request.model_dump()
        payload["model_path"] = DEFAULT_MODEL_PATH
        payload["people_rows"] = _runtime_people_rows()
        payload["use_database"] = True
        results = recommender_service.generate_recommendations(payload)
        _record_learning_event(
            "recommendation_generated",
            entity_type="proposal",
            summary="Generated volunteer recommendation",
            payload={"request": payload, "results": results},
            text=" ".join([
                request.proposal_text or "",
                request.village_name or "",
                " ".join(request.required_skills or []),
            ]),
        )
        
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


@app.post("/api/v1/insights/chat")
async def insights_chat_endpoint(request: InsightChatRequest):
    try:
        response = analyze_coordinator_query(
            request.query,
            problems=PROBLEMS,
            volunteers=VOLUNTEERS,
            days_back=request.days_back,
            limit=request.limit,
        )
        _record_learning_event(
            "insights_chat",
            entity_type="query",
            summary=request.query,
            payload={"request": request.model_dump(), "response": response},
            text=request.query,
        )
        return response
    except Exception as exc:
        logger.exception("Insights chat failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/insights/overview")
async def insights_overview_endpoint(days_back: int = 30):
    try:
        response = build_insight_overview(PROBLEMS, VOLUNTEERS, days_back=days_back)
        _record_learning_event(
            "insights_overview",
            entity_type="query",
            summary=f"Overview requested for {days_back} days",
            payload={"days_back": days_back, "response": response},
            text=f"overview {days_back} days",
        )
        return response
    except Exception as exc:
        logger.exception("Insights overview failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/insights/briefing")
async def insights_briefing_endpoint(days_back: int = 7):
    try:
        response = build_weekly_briefing(PROBLEMS, VOLUNTEERS, days_back=days_back)
        _record_learning_event(
            "weekly_briefing",
            entity_type="query",
            summary=f"Weekly briefing requested for {days_back} days",
            payload={"days_back": days_back, "response": response},
            text=f"weekly briefing {days_back} days",
        )
        return response
    except Exception as exc:
        logger.exception("Weekly briefing generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/problems/{problem_id}/timeline")
async def problem_timeline_endpoint(problem_id: str):
    problem = next((item for item in PROBLEMS if item["id"] == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    try:
        return _problem_timeline(problem)
    except Exception as exc:
        logger.exception("Problem timeline lookup failed for %s", problem_id)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/learning/events")
async def learning_events_endpoint(
    limit: int = 50,
    event_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
):
    try:
        return {
            "events": DATA_STORE.get_recent_learning_events(
                limit=limit,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        }
    except Exception as exc:
        logger.exception("Learning events lookup failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/playbooks", response_model=List[PlaybookResponse])
async def playbooks_endpoint(
    topic: Optional[str] = None,
    village_name: Optional[str] = None,
    limit: int = 25,
):
    try:
        rows = DATA_STORE.list_playbooks(topic=topic, village_name=village_name, limit=limit)
        return [
            {
                "id": row["id"],
                "topic": row.get("topic") or row.get("data", {}).get("topic") or "general",
                "village_name": row.get("village_name") or row.get("data", {}).get("village_name"),
                "title": row.get("data", {}).get("title") or row["id"],
                "summary": row.get("data", {}).get("summary") or "",
                "materials": list(row.get("data", {}).get("materials") or []),
                "safety_notes": list(row.get("data", {}).get("safety_notes") or []),
                "steps": list(row.get("data", {}).get("steps") or []),
                "source_problem_id": row.get("data", {}).get("source_problem_id"),
                "source_problem_title": row.get("data", {}).get("source_problem_title"),
                "created_at": row.get("data", {}).get("created_at") or row.get("updated_at") or _now_iso(),
            }
            for row in rows
        ]
    except Exception as exc:
        logger.exception("Playbooks lookup failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/inventory", response_model=List[InventoryItemResponse])
async def inventory_list_endpoint(
    owner_type: Optional[str] = None,
    owner_id: Optional[str] = None,
):
    try:
        rows = DATA_STORE.list_inventory(owner_type=owner_type, owner_id=owner_id)
        return [
            {
                "id": row["id"],
                "owner_type": row["owner_type"],
                "owner_id": row["owner_id"],
                "item_name": row["item_name"],
                "quantity": row["quantity"],
                "notes": row.get("data", {}).get("notes"),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
    except Exception as exc:
        logger.exception("Inventory lookup failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/inventory", response_model=InventoryItemResponse)
async def inventory_upsert_endpoint(request: InventoryItemRequest):
    try:
        return DATA_STORE.upsert_inventory_item(
            owner_type=request.owner_type,
            owner_id=request.owner_id,
            item_name=request.item_name,
            quantity=request.quantity,
            data={"notes": request.notes},
        )
    except Exception as exc:
        logger.exception("Inventory update failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/escalations", response_model=EscalationResponse)
async def escalations_endpoint(days_back: int = 7):
    try:
        cutoff = datetime.now() - timedelta(days=max(1, days_back))
        items = []
        for problem in PROBLEMS:
            if problem.get("status") == "completed":
                continue
            created_raw = problem.get("created_at") or problem.get("updated_at")
            created_dt = None
            if created_raw:
                try:
                    created_dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    if created_dt.tzinfo:
                        created_dt = created_dt.astimezone(timezone.utc).replace(tzinfo=None)
                except ValueError:
                    created_dt = None
            if created_dt and created_dt < cutoff:
                continue
            items.append(_escalation_level(problem))
        items = [item for item in items if item["escalation_level"] != "watch"]
        items.sort(key=lambda item: (item["age_hours"], item["severity"]), reverse=True)
        return {
            "generated_at": _now_iso(),
            "window_days": days_back,
            "overdue_count": len(items),
            "items": items[:50],
        }
    except Exception as exc:
        logger.exception("Escalation scan failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/reputation", response_model=ReputationResponse)
async def reputation_endpoint(days_back: int = 90):
    try:
        return {
            "generated_at": _now_iso(),
            "window_days": days_back,
            "volunteers": _volunteer_reputation(PROBLEMS, VOLUNTEERS, days_back=days_back),
        }
    except Exception as exc:
        logger.exception("Reputation scan failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/routes/optimizer", response_model=RouteOptimizerResponse)
async def route_optimizer_endpoint(days_back: int = 14):
    try:
        return {
            "generated_at": _now_iso(),
            "window_days": days_back,
            "routes": _route_optimizer(PROBLEMS, VOLUNTEERS, days_back=days_back),
        }
    except Exception as exc:
        logger.exception("Route optimization failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/insights/seasonal-risk", response_model=SeasonalRiskResponse)
async def seasonal_risk_endpoint(days_back: int = 365):
    try:
        return build_seasonal_risk_forecast(PROBLEMS, days_back=days_back)
    except Exception as exc:
        logger.exception("Seasonal risk forecast failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/maintenance/plan", response_model=MaintenancePlanResponse)
async def maintenance_plan_endpoint(days_back: int = 180):
    try:
        return build_preventive_maintenance_plan(PROBLEMS, VOLUNTEERS, days_back=days_back)
    except Exception as exc:
        logger.exception("Preventive maintenance plan failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/hotspots/heatmap", response_model=HeatmapResponse)
async def hotspot_heatmap_endpoint(days_back: int = 90):
    try:
        return build_hotspot_heatmap(PROBLEMS, days_back=days_back)
    except Exception as exc:
        logger.exception("Hotspot heatmap failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/campaigns/plan", response_model=CampaignModeResponse)
async def campaign_mode_endpoint(days_back: int = 30, topic: Optional[str] = None):
    try:
        return build_campaign_mode_plan(PROBLEMS, VOLUNTEERS, days_back=days_back, focus_topic=topic)
    except Exception as exc:
        logger.exception("Campaign mode planning failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/broadcasts")
async def create_broadcast_endpoint(request: BroadcastRequest):
    try:
        broadcast_id = f"broadcast-{uuid.uuid4().hex[:12]}"
        scheduled_for = request.scheduled_for.strip() if request.scheduled_for else None
        status = request.status or ("scheduled" if scheduled_for else "sent")
        record = DATA_STORE.upsert_platform_record(
            record_type="broadcast",
            record_id=broadcast_id,
            owner_id=request.owner_id,
            subtype=request.event_type,
            status=status,
            data={
                "id": broadcast_id,
                "title": request.title,
                "message": request.message,
                "event_type": request.event_type,
                "audience_type": request.audience_type,
                "target_villages": request.target_villages,
                "target_volunteers": request.target_volunteers,
                "target_skills": request.target_skills,
                "tags": request.tags,
                "media_ids": request.media_ids,
                "scheduled_for": scheduled_for,
                "delivery_state": status,
                "created_at": _now_iso(),
            },
        )
        payload = build_broadcast_feed([record], limit=1)
        broadcast = payload["items"][0] if payload["items"] else record
        _record_learning_event(
            "broadcast_created",
            entity_type="broadcast",
            entity_id=broadcast_id,
            summary=f"Created {request.event_type} broadcast",
            payload=broadcast,
            text=" ".join([
                request.title,
                request.message,
                request.event_type,
                " ".join(request.tags or []),
                " ".join(request.target_villages or []),
                " ".join(request.target_volunteers or []),
                " ".join(request.target_skills or []),
            ]),
        )
        return {"status": "success", "broadcast": broadcast}
    except Exception as exc:
        logger.exception("Broadcast creation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/broadcasts", response_model=BroadcastFeedResponse)
async def list_broadcasts_endpoint(
    audience: str = "all",
    village_name: Optional[str] = None,
    volunteer_id: Optional[str] = None,
    volunteer_skills: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 20,
):
    try:
        records = DATA_STORE.list_platform_records(record_type="broadcast", limit=max(1, min(1000, int(limit))))
        payload = build_broadcast_feed(
            records,
            scope=audience if audience in {"all", "villages", "volunteers"} else "all",
            village_name=village_name,
            volunteer_id=volunteer_id,
            volunteer_skills=[part.strip() for part in (volunteer_skills or "").split(",") if part.strip()],
            tags=[part.strip() for part in (tags or "").split(",") if part.strip()],
            limit=limit,
        )
        return payload
    except Exception as exc:
        logger.exception("Broadcast feed failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/analytics/feedback", response_model=ResidentFeedbackAnalyticsResponse)
async def resident_feedback_analytics_endpoint(days_back: int = 90):
    try:
        feedback_rows = DATA_STORE.list_followup_feedback(limit=1000)
        return build_resident_feedback_summary(PROBLEMS, feedback_rows, VOLUNTEERS, days_back=days_back)
    except Exception as exc:
        logger.exception("Resident feedback analytics failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/analytics/repeat-breakdown", response_model=RepeatBreakdownResponse)
async def repeat_breakdown_endpoint(days_back: int = 90):
    try:
        return build_repeat_breakdown_metrics(PROBLEMS, days_back=days_back)
    except Exception as exc:
        logger.exception("Repeat breakdown analytics failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/platform/overview")
async def platform_overview_endpoint(days_back: int = 180):
    try:
        villages = DATA_STORE.get_village_name_rows()
        records = {
            "assets": DATA_STORE.list_platform_records(record_type="asset", limit=100),
            "procurement": DATA_STORE.list_platform_records(record_type="procurement", limit=100),
            "privacy": DATA_STORE.list_platform_records(record_type="privacy_setting", limit=50),
            "certifications": DATA_STORE.list_platform_records(record_type="certification", limit=100),
            "shifts": DATA_STORE.list_platform_records(record_type="shift_plan", limit=50),
            "training": DATA_STORE.list_platform_records(record_type="training_module", limit=50),
            "burnout": DATA_STORE.list_platform_records(record_type="burnout_signal", limit=100),
            "suggestions": DATA_STORE.list_platform_records(record_type="suggestion", limit=50),
            "polls": DATA_STORE.list_platform_records(record_type="poll", limit=50),
            "announcements": DATA_STORE.list_platform_records(record_type="announcement", limit=50),
            "champions": DATA_STORE.list_platform_records(record_type="champion", limit=50),
            "forms": DATA_STORE.list_platform_records(record_type="custom_form", limit=50),
            "webhooks": DATA_STORE.list_platform_records(record_type="webhook_event", limit=50),
            "memory": DATA_STORE.list_platform_records(record_type="conversation_memory", limit=20),
            "broadcasts": DATA_STORE.list_platform_records(record_type="broadcast", limit=100),
        }
        overview = {
            "generated_at": _now_iso(),
            "window_days": days_back,
            "asset_registry": build_asset_registry(PROBLEMS, days_back=days_back),
            "procurement_tracker": build_procurement_tracker(PROBLEMS, days_back=days_back),
            "district_hierarchy": build_district_hierarchy(PROBLEMS, villages, days_back=days_back),
            "work_order_templates": build_work_order_templates(),
            "proof_spoofing": [assess_proof_spoofing(problem) for problem in PROBLEMS if problem.get("proof")],
            "resident_confirmation": [build_resident_confirmation(problem) for problem in PROBLEMS if problem.get("status") != "completed"][:10],
            "skill_certifications": build_skill_certifications(VOLUNTEERS, PROBLEMS),
            "shift_plan": build_shift_plan(VOLUNTEERS, PROBLEMS),
            "training_mode": build_training_mode(),
            "burnout_signals": assess_burnout_signals(VOLUNTEERS, PROBLEMS),
            "suggestion_box": build_suggestion_box(records["suggestions"]),
            "community_polls": build_community_polls(records["polls"]),
            "announcements": build_announcement_feed(records["announcements"]),
            "village_champions": build_village_champions(records["champions"]),
            "broadcasts": build_broadcast_feed(records["broadcasts"], limit=20)["items"],
            "impact": build_impact_measurement(PROBLEMS),
            "ab_tests": build_ab_test_plan(PROBLEMS),
            "anomalies": build_anomaly_dashboard(PROBLEMS),
            "budget_forecast": build_budget_forecast(PROBLEMS),
            "forms": build_custom_forms_bundle(records["forms"]),
            "webhook_events": build_webhook_events(records["webhooks"]),
            "conversation_memory": build_conversation_memory(records["memory"]),
            "record_counts": {key: len(value) for key, value in records.items()},
        }
        _record_learning_event(
            "platform_overview",
            entity_type="query",
            summary=f"Platform overview requested for {days_back} days",
            payload={"days_back": days_back, "response": overview},
            text="platform overview",
        )
        return overview
    except Exception as exc:
        logger.exception("Platform overview failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/platform/records/{record_type}")
async def platform_records_list_endpoint(
    record_type: str,
    subtype: Optional[str] = None,
    owner_id: Optional[str] = None,
    limit: int = 50,
):
    try:
        return {
            "record_type": record_type,
            "items": DATA_STORE.list_platform_records(
                record_type=record_type,
                subtype=subtype,
                owner_id=owner_id,
                limit=limit,
            ),
        }
    except Exception as exc:
        logger.exception("Platform record lookup failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/platform/records/{record_type}")
async def platform_records_upsert_endpoint(record_type: str, request: PlatformRecordRequest):
    try:
        record_id = request.record_id or f"{record_type}-{uuid.uuid4().hex[:12]}"
        payload = DATA_STORE.upsert_platform_record(
            record_type=record_type,
            record_id=record_id,
            subtype=request.subtype,
            owner_id=request.owner_id,
            status=request.status,
            data=request.data,
        )
        _record_learning_event(
            f"platform_record_{record_type}",
            entity_type="platform_record",
            entity_id=record_id,
            summary=f"Upserted {record_type} record",
            payload=payload,
            text=" ".join([
                record_type,
                str(request.subtype or ""),
                str(request.owner_id or ""),
                json.dumps(request.data, ensure_ascii=False),
            ]),
        )
        return payload
    except Exception as exc:
        logger.exception("Platform record upsert failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/platform/resident-confirmation/{problem_id}")
async def resident_confirmation_endpoint(problem_id: str, request: ResidentConfirmationRequest):
    problem = next((item for item in PROBLEMS if item.get("id") == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    confirmation = {
        "id": f"confirm-{problem_id}-{uuid.uuid4().hex[:8]}",
        "problem_id": problem_id,
        "source": request.source,
        "response": request.response,
        "note": request.note,
        "reporter_name": request.reporter_name,
        "reporter_phone": request.reporter_phone,
        "created_at": _now_iso(),
    }
    DATA_STORE.upsert_platform_record(
        record_type="resident_confirmation",
        record_id=confirmation["id"],
        owner_id=problem_id,
        status=request.response,
        data=confirmation,
    )
    if request.response == "resolved":
        problem["status"] = "completed"
        problem["updated_at"] = _now_iso()
        persist_runtime_state()
    _record_learning_event(
        "resident_confirmation",
        entity_type="problem",
        entity_id=problem_id,
        summary=f"Resident confirmation: {request.response}",
        payload=confirmation,
        text=" ".join([problem.get("title", ""), request.response, request.note or ""]),
    )
    return {"status": "success", "confirmation": confirmation, "problem": _serialize_problem(problem)}


@app.get("/api/v1/platform/audit-pack/{problem_id}")
async def audit_pack_endpoint(problem_id: str):
    problem = next((item for item in PROBLEMS if item.get("id") == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    timeline = _problem_timeline(problem)["timeline"]
    learning_events = DATA_STORE.get_recent_learning_events(limit=50, entity_type="problem", entity_id=problem_id)
    return build_audit_pack(problem, timeline, learning_events)


@app.post("/api/v1/platform/form-autofill")
async def form_autofill_endpoint(request: ProblemTextRequest):
    return autofill_problem_form(request.text, village_name=request.village_name)


@app.get("/api/v1/platform/case-similarity/{problem_id}")
async def case_similarity_endpoint(problem_id: str):
    problem = next((item for item in PROBLEMS if item.get("id") == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return find_case_similarity_explorer(problem, PROBLEMS)


@app.post("/api/v1/platform/policy")
async def policy_question_endpoint(request: PolicyQuestionRequest):
    return answer_policy_question(request.question)


@app.get("/api/v1/platform/export")
async def platform_export_endpoint():
    platform_records: List[Dict[str, Any]] = []
    for record_type in [
        "asset",
        "procurement",
        "privacy_setting",
        "certification",
        "shift_plan",
        "training_module",
        "burnout_signal",
        "suggestion",
        "poll",
        "announcement",
        "champion",
        "custom_form",
        "webhook_event",
        "conversation_memory",
        "resident_confirmation",
        "broadcast",
    ]:
        platform_records.extend(DATA_STORE.list_platform_records(record_type=record_type, limit=1000))
    return build_bulk_export_bundle(PROBLEMS, VOLUNTEERS, platform_records)


@app.get("/api/v1/problems/{problem_id}/evidence-comparison", response_model=EvidenceComparisonResponse)
async def evidence_comparison_endpoint(problem_id: str):
    problem = next((item for item in PROBLEMS if item.get("id") == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    proof = problem.get("proof") or {}
    if not proof:
        raise HTTPException(status_code=404, detail="No proof has been submitted for this problem")

    before_media_id = proof.get("before_media_id")
    after_media_id = proof.get("after_media_id")
    before_asset = _asset_by_id(before_media_id) if before_media_id else None
    after_asset = _asset_by_id(after_media_id) if after_media_id else None
    verification = proof.get("verification") or {}

    return {
        "generated_at": _now_iso(),
        "problem_id": problem_id,
        "title": problem.get("title") or problem_id,
        "status": problem.get("status") or "pending",
        "before_media_id": before_media_id,
        "after_media_id": after_media_id,
        "before_url": before_asset.get("url") if before_asset else None,
        "after_url": after_asset.get("url") if after_asset else None,
        "accepted": bool(verification.get("accepted")),
        "confidence": float(verification.get("confidence") or 0.0),
        "summary": str(verification.get("summary") or "No comparison summary available."),
        "detected_change": str(verification.get("detected_change") or "unknown"),
        "source": str(verification.get("source") or "stored-proof"),
    }


@app.post("/problems/{problem_id}/follow-up-feedback")
async def problem_follow_up_feedback_endpoint(problem_id: str, request: FollowUpFeedbackRequest):
    problem = next((item for item in PROBLEMS if item.get("id") == problem_id), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    try:
        volunteer_id = request.volunteer_id or _problem_primary_volunteer_id(problem)
        feedback_payload = request.model_dump()
        if volunteer_id:
            feedback_payload["volunteer_id"] = volunteer_id
        stored = DATA_STORE.record_followup_feedback(
            problem_id=problem_id,
            source=request.source,
            response=request.response,
            data=feedback_payload,
        )
        if request.response != "resolved":
            problem["status"] = "in_progress"
            problem["updated_at"] = _now_iso()
            persist_runtime_state()
        _record_learning_event(
            "problem_followup_feedback",
            entity_type="problem",
            entity_id=problem_id,
            summary=f"Follow-up feedback: {request.response}",
            payload={"problem_id": problem_id, "feedback": stored},
            text=" ".join([
                problem.get("title", ""),
                problem.get("description", ""),
                request.response,
                request.note or "",
            ]),
        )
        return {"status": "success", "feedback": stored, "problem": _serialize_problem(problem)}
    except Exception as exc:
        logger.exception("Follow-up feedback failed for %s", problem_id)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/public/status-board", response_model=PublicStatusBoardResponse)
async def public_status_board_endpoint(
    village_name: Optional[str] = None,
    status: Optional[str] = None,
    days_back: int = 60,
):
    try:
        response = _public_status_board(
            PROBLEMS,
            village_name=village_name,
            status_filter=status,
            days_back=days_back,
        )
        _record_learning_event(
            "public_status_board_viewed",
            entity_type="query",
            summary="Public status board viewed",
            payload={"village_name": village_name, "status": status, "days_back": days_back},
            text="public status board",
        )
        return response
    except Exception as exc:
        logger.exception("Public status board failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/submit-problem")
async def submit_problem_endpoint(request: ProblemRequest):
    try:
        reporter_id = request.villager_id or request.coordinator_id or f"villager-{uuid.uuid4().hex[:8]}"
        reporter_profile = _find_profile(reporter_id)
        if not reporter_profile:
            reporter_profile = _upsert_profile({
                "id": reporter_id,
                "email": None,
                "full_name": request.reporter_name or "Village Resident",
                "phone": request.reporter_phone,
                "role": "villager",
                "village_name": request.village_name,
            })

        lat, lng = _village_coordinates(request.village_name)
        
        # Auto-infer severity from text and tags if not supplied by the user
        if request.severity:
            severity = request.severity.upper()
            severity_source = "User Selected"
        else:
            tags = request.visual_tags or []
            severity = infer_problem_severity(request.title, request.description, tags)
            severity_source = "AI Inferred"

        duplicate_candidates = find_duplicate_problem_candidates(
            PROBLEMS,
            title=request.title,
            description=request.description,
            village_name=request.village_name,
            category=request.category,
            visual_tags=request.visual_tags,
            transcript=request.transcript,
            limit=3,
        )
        best_duplicate = duplicate_candidates[0] if duplicate_candidates else None
        if best_duplicate and float(best_duplicate.get("score") or 0.0) >= 0.78:
            target_problem = next((problem for problem in PROBLEMS if problem.get("id") == best_duplicate["problem_id"]), None)
            if target_problem and target_problem.get("status") != "completed":
                duplicate_report = _attach_duplicate_report(
                    target_problem,
                    request=request,
                    duplicate_score=float(best_duplicate.get("score") or 0.0),
                    duplicate_reason=str(best_duplicate.get("reason") or "Likely duplicate report"),
                    matched_problem_id=str(best_duplicate["problem_id"]),
                )
                _record_learning_event(
                    "problem_duplicate_attached",
                    entity_type="problem",
                    entity_id=str(target_problem.get("id")),
                    summary=f"Attached duplicate report to {target_problem.get('id')}",
                    payload={
                        "target_problem_id": target_problem.get("id"),
                        "duplicate_report": duplicate_report,
                        "source_submission": request.model_dump(),
                    },
                    text=" ".join([
                        request.title,
                        request.description,
                        request.category or "",
                        request.village_name or "",
                        str(best_duplicate.get("reason") or ""),
                    ]),
                )
                persist_runtime_state()
                return {
                    "status": "duplicate_attached",
                    "id": str(target_problem.get("id")),
                    "duplicate_of": str(target_problem.get("id")),
                    "duplicate_report": duplicate_report,
                    "duplicate_candidates": duplicate_candidates,
                }

        new_id = f"prob-{uuid.uuid4().hex[:12]}"
        new_problem = {
            "id": new_id,
            "villager_id": reporter_id,
            "title": request.title,
            "description": request.description,
            "category": request.category,
            "severity": severity,
            "severity_source": severity_source,
            "village_name": request.village_name,
            "village_address": request.village_address,
            "visual_tags": request.visual_tags or [],
            "has_audio": bool(request.has_audio),
            "media_ids": list(request.media_ids or []),
            "transcript": request.transcript,
            "transcript_language": request.transcript_language,
            "status": "pending",
            "lat": lat,
            "lng": lng,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "profiles": reporter_profile,
            "matches": [],
            "duplicate_reports": [],
        }
        PROBLEMS.insert(0, new_problem)
        _record_learning_event(
            "problem_reported",
            entity_type="problem",
            entity_id=new_id,
            summary=f"Problem reported: {request.title}",
            payload={"problem": new_problem},
            text=" ".join([
                request.title,
                request.description,
                request.category,
                request.village_name or "",
                " ".join(request.visual_tags or []),
            ]),
        )
        persist_runtime_state()
        logger.info(f"Problem submitted: {request.title!r} in {request.village_name} severity={severity} ({severity_source})")
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
            transcription = transcribe_audio(tmp_path)
            return transcription
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
    print("Starting Gram Connect Backend Server...")
    print(f"Loading data from: {DATASET_ROOT}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
