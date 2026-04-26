import os
import logging
import csv
import json
import hashlib
import mimetypes
import threading
import uuid
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import shutil
import tempfile

from env_loader import load_local_env
from demo_bootstrap import ensure_canonical_dataset, should_bootstrap_models
from recommender_service import RecommenderService
from multimodal_service import transcribe_audio, analyze_image, verify_resolution_proof
from notification_service import notify_problem_resolved, notify_team_assignment
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

# Initialize Service
recommender_service = RecommenderService(
    model_path=DEFAULT_MODEL_PATH,
    people_csv=DEFAULT_PEOPLE_CSV,
    dataset_root=DATASET_ROOT
)

app = FastAPI(title="Gram Connect Backend Service")

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
    role: str = Field("villager", pattern="^(villager|volunteer|coordinator)$")
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/villages")
async def list_villages():
    """Return all known villages with coordinates for map autocomplete."""
    try:
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

# --- In-Memory State & Data Loading ---
# We use in-memory lists to simulate a database for this session.
# In a real app, this would be replaced by SQL queries.

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
    # Secondary: read from village_locations.csv at runtime to pick up any additions
    try:
        rows = read_csv_norm(DEFAULT_VILLAGE_LOCATIONS)
        for r in rows:
            name = get_any(r, ["village_name", "village", "name"])
            lat_raw = get_any(r, ["lat", "latitude"])
            lng_raw = get_any(r, ["lng", "longitude"])
            if name and lat_raw and lng_raw:
                try:
                    village_coords.setdefault(name, (float(lat_raw), float(lng_raw)))
                except ValueError:
                    pass
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


def _normalize_availability(volunteer: Dict[str, Any]) -> str:
    value = (
        volunteer.get("availability")
        or volunteer.get("availability_status")
        or "available"
    )
    return str(value).strip().lower() or "available"


def _runtime_people_rows() -> List[Dict[str, Any]]:
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

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as handle:
        fieldnames = list(personalized_rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in personalized_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
        people_csv = handle.name

    scored_candidates: List[tuple[float, int, Dict[str, Any]]] = []
    try:
        for problem in open_problems:
            payload = _recommendation_payload_for_problem(problem, people_csv=people_csv)
            payload["team_size"] = 1
            payload["num_teams"] = 1
            try:
                results = recommender_service.generate_recommendations(payload)
            except Exception as exc:
                logger.warning("Failed to score problem %s for volunteer %s: %s", problem.get("id"), volunteer_id, exc)
                continue
            top_team = (results.get("teams") or [{}])[0]
            score = float(top_team.get("goodness") or 0.0)
            lexical = _problem_relevance_score(problem, volunteer)
            scored_candidates.append((score, lexical, problem))
    finally:
        try:
            os.remove(people_csv)
        except OSError:
            pass

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
    people_csv = _sync_runtime_people_csv()
    reassigned = 0

    for problem in PROBLEMS:
        if problem.get("status") == "completed":
            continue

        payload = _recommendation_payload_for_problem(problem, people_csv=people_csv)
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
        STATE_VERSION += 1
    # Persistence is disabled for this session so we always get a fresh run from CSVs.
    pass


def _match_targets_volunteer(match: Dict[str, Any], volunteer_id: str) -> bool:
    volunteer = match.get("volunteers", {})
    return (
        match.get("volunteer_id") == volunteer_id
        or volunteer.get("user_id") == volunteer_id
        or volunteer.get("id") == volunteer_id
    )


def load_initial_data(force_seed: bool = False):
    """Loads seeded runtime state backed by canonical CSV data."""
    global PROBLEMS, VOLUNTEERS, PROFILES, MEDIA_ASSETS, STATE_VERSION

    if False and os.path.exists(RUNTIME_STATE_JSON) and not force_seed:
        try:
            with open(RUNTIME_STATE_JSON, "r", encoding="utf-8") as handle:
                state = json.load(handle)
            STATE_VERSION = int(state.get("state_version", 0) or 0)
            PROBLEMS = list(state.get("problems", []))
            VOLUNTEERS = list(state.get("volunteers", []))
            PROFILES = list(state.get("profiles", []))
            MEDIA_ASSETS = list(state.get("media_assets", []))
            if PROBLEMS and VOLUNTEERS:
                if not PROFILES:
                    PROFILES = _build_seed_profiles(_load_profile_directory(), VOLUNTEERS, PROBLEMS)
                    persist_runtime_state()
                _sync_runtime_people_csv()
                return
        except Exception as exc:
            logger.warning("Failed to load runtime state, rebuilding from canonical dataset: %s", exc)

    try:
        profile_directory = _load_profile_directory()
        VOLUNTEERS = _build_seed_volunteers(profile_directory)
        volunteers_by_id = {volunteer["id"]: volunteer for volunteer in VOLUNTEERS}
        PROBLEMS = _build_seed_problems(profile_directory, volunteers_by_id)
        PROFILES = _build_seed_profiles(profile_directory, VOLUNTEERS, PROBLEMS)
        MEDIA_ASSETS = []
        STATE_VERSION = max(STATE_VERSION, 0)
        _sync_runtime_people_csv()
        persist_runtime_state()
    except Exception as exc:
        logger.error("Failed to load canonical seed data: %s", exc)
        PROBLEMS = []
        VOLUNTEERS = []
        PROFILES = []
        MEDIA_ASSETS = []
        STATE_VERSION = 0


def reset_runtime_state() -> None:
    if os.path.exists(RUNTIME_STATE_JSON):
        os.remove(RUNTIME_STATE_JSON)
    load_initial_data(force_seed=True)

# Load data on startup (or module import)
load_initial_data()


@app.on_event("startup")
async def bootstrap_demo_runtime():
    """Forge engine requires no trained model — just seed the dataset and runtime state."""
    if not should_bootstrap_models():
        return
    try:
        ensure_canonical_dataset()
        reset_runtime_state()
        logger.info("Demo runtime bootstrapped (Forge engine — no model training required).")
    except Exception as exc:
        logger.exception("Demo bootstrap failed: %s", exc)


@app.post("/train")
def train_endpoint():
    """Deprecated: Forge engine uses no ML model. Training is no longer required."""
    return {
        "status": "deprecated",
        "message": "The Forge scoring engine is deterministic and requires no trained model. This endpoint is a no-op.",
    }


@app.get("/problems")
async def get_problems():
    return _serialize_problems(PROBLEMS)


@app.get("/state-version")
async def get_state_version():
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
    if new_status == "completed":
        completed_at = _now_iso()
        for match in problem.get("matches", []):
            match["completed_at"] = match.get("completed_at") or completed_at
        villager_phone = (
            problem.get("profiles", {}).get("phone")
            or problem.get("profile", {}).get("phone")
        )
        notify_problem_resolved(villager_phone, problem.get("title", "Reported issue"))
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
    persist_runtime_state()
    return {"status": "success", "problem": _serialize_problem(problem), "proof": proof}


@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(request: RecommendRequest):
    try:
        payload = request.model_dump()
        payload["model_path"] = DEFAULT_MODEL_PATH
        payload["people_csv"] = _sync_runtime_people_csv()
        results = recommender_service.generate_recommendations(payload)
        
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
        
        # Auto-infer severity from text if not supplied by the user
        full_text = " ".join(filter(None, [request.title, request.description]))
        if request.severity:
            severity = request.severity.upper()
            severity_source = "User Selected"
        else:
            from forge import estimate_severity, SEVERITY_LABELS
            severity = SEVERITY_LABELS.get(estimate_severity(full_text), "NORMAL")
            severity_source = "Auto-detected"

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
        }
        PROBLEMS.insert(0, new_problem)
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
