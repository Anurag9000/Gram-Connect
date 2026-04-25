import asyncio
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import UploadFile
from fastapi.exceptions import HTTPException

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_server


def test_health_endpoint():
    assert asyncio.run(api_server.health()) == {"status": "ok"}


@patch("api_server.train_model")
def test_train_endpoint(mock_train):
    mock_train.return_value = 0.85
    request = api_server.TrainRequest(out="ignored-output.bin")
    response = api_server.train_endpoint(request)
    assert response.status == "ok"
    assert response.auc == 0.85
    assert response.model_path.endswith("backend/runtime_data/canonical_model.pkl")


@patch("api_server.notify_team_assignment")
@patch.object(api_server.recommender_service, "generate_recommendations")
def test_recommend_endpoint(mock_generate, mock_notify):
    mock_generate.return_value = {
        "severity_detected": "NORMAL",
        "severity_source": "auto",
        "proposal_location": "Village A",
        "teams": [{"team_ids": "p1", "team_names": "Volunteer 1", "members": []}],
    }

    request = api_server.RecommendRequest(
        proposal_text="Test proposal",
        task_start="2026-01-01T10:00:00",
        task_end="2026-01-01T12:00:00",
        village_name="Village A",
    )
    response = api_server.recommend_endpoint(request)

    assert response.severity_detected == "NORMAL"
    mock_notify.assert_called_once()


@patch("api_server.transcribe_audio")
def test_transcribe_endpoint(mock_transcribe):
    mock_transcribe.return_value = {"text": "Transcribed text", "language": "en", "source": "gemini"}
    upload = UploadFile(filename="sample.mp3", file=io.BytesIO(b"audio"))
    response = api_server.transcribe_endpoint(upload)
    assert response["text"] == "Transcribed text"
    assert response["language"] == "en"


@patch("api_server.analyze_image")
def test_analyze_image_endpoint(mock_analyze):
    mock_analyze.return_value = {"top_label": "Infrastructure", "confidence": 0.9}
    upload = UploadFile(filename="sample.jpg", file=io.BytesIO(b"image"))
    response = api_server.analyze_image_endpoint(upload)
    assert response["top_label"] == "Infrastructure"


@patch("api_server.verify_resolution_proof")
def test_submit_proof_requires_gemini_acceptance(mock_verify, tmp_path):
    original_state_path = api_server.RUNTIME_STATE_JSON
    original_media_root = api_server.MEDIA_ROOT
    api_server.RUNTIME_STATE_JSON = str(tmp_path / "app_state.json")
    api_server.MEDIA_ROOT = tmp_path / "media"
    api_server.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    problem = {
        "id": "problem-proof-verify",
        "title": "Broken pump",
        "description": "Pump is damaged near school",
        "category": "infrastructure",
        "village_name": "Sundarpur",
        "status": "in_progress",
        "matches": [],
        "media_ids": [],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T10:00:00",
        "visual_tags": ["broken pump"],
    }
    api_server.PROBLEMS.append(problem)
    try:
        after_media = asyncio.run(
            api_server.upload_media(
                file=UploadFile(filename="after.jpg", file=io.BytesIO(b"after-bytes")),
                kind="proof_after",
                problem_id=problem["id"],
                volunteer_id="mock-volunteer-uuid",
            )
        )["media"]

        mock_verify.return_value = {
            "accepted": True,
            "confidence": 0.91,
            "task_match": True,
            "same_scene": True,
            "issue_fixed": True,
            "summary": "The handpump appears repaired and functional.",
            "detected_change": "repair completed",
            "source": "gemini",
        }
        response = asyncio.run(
            api_server.submit_proof(
                problem["id"],
                api_server.ProofRequest(
                    volunteer_id="mock-volunteer-uuid",
                    after_media_id=after_media["id"],
                    notes="completed",
                ),
            )
        )
        assert response["status"] == "success"
        assert response["proof"]["verification"]["accepted"] is True
        assert problem["status"] == "completed"
    finally:
        api_server.PROBLEMS[:] = [item for item in api_server.PROBLEMS if item.get("id") != problem["id"]]
        api_server.MEDIA_ASSETS[:] = [item for item in api_server.MEDIA_ASSETS if item.get("problem_id") != problem["id"]]
        api_server.RUNTIME_STATE_JSON = original_state_path
        api_server.MEDIA_ROOT = original_media_root


@patch("api_server.verify_resolution_proof")
def test_submit_proof_rejects_invalid_before_after(mock_verify, tmp_path):
    original_state_path = api_server.RUNTIME_STATE_JSON
    original_media_root = api_server.MEDIA_ROOT
    api_server.RUNTIME_STATE_JSON = str(tmp_path / "app_state.json")
    api_server.MEDIA_ROOT = tmp_path / "media"
    api_server.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    problem = {
        "id": "problem-proof-reject",
        "title": "Blocked drain",
        "description": "Drain is clogged near market",
        "category": "sanitation",
        "village_name": "Sundarpur",
        "status": "in_progress",
        "matches": [],
        "media_ids": [],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T10:00:00",
        "visual_tags": ["drain"],
    }
    api_server.PROBLEMS.append(problem)
    try:
        after_media = asyncio.run(
            api_server.upload_media(
                file=UploadFile(filename="after.jpg", file=io.BytesIO(b"after-bytes")),
                kind="proof_after",
                problem_id=problem["id"],
                volunteer_id="mock-volunteer-uuid",
            )
        )["media"]

        mock_verify.return_value = {
            "accepted": False,
            "confidence": 0.12,
            "task_match": False,
            "same_scene": False,
            "issue_fixed": False,
            "summary": "The uploaded images do not show the same drain being fixed.",
            "detected_change": "no verifiable repair",
            "source": "gemini",
        }
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                api_server.submit_proof(
                    problem["id"],
                    api_server.ProofRequest(
                        volunteer_id="mock-volunteer-uuid",
                        after_media_id=after_media["id"],
                        notes="completed",
                    ),
                )
            )
        assert exc_info.value.status_code == 400
        assert "do not show the same drain" in str(exc_info.value.detail)
        assert problem["status"] == "in_progress"
    finally:
        api_server.PROBLEMS[:] = [item for item in api_server.PROBLEMS if item.get("id") != problem["id"]]
        api_server.MEDIA_ASSETS[:] = [item for item in api_server.MEDIA_ASSETS if item.get("problem_id") != problem["id"]]
        api_server.RUNTIME_STATE_JSON = original_state_path
        api_server.MEDIA_ROOT = original_media_root


def test_submit_problem_persists_runtime_state(tmp_path):
    original_state_path = api_server.RUNTIME_STATE_JSON
    api_server.RUNTIME_STATE_JSON = str(tmp_path / "app_state.json")
    created_id = None
    try:
        response = asyncio.run(
            api_server.submit_problem_endpoint(
                api_server.ProblemRequest(
                    title="Broken handpump",
                    description="Needs urgent repair",
                    category="water",
                    village_name="Bhavani Kheda",
                    village_address="Near the school",
                    coordinator_id="coord-1",
                    visual_tags=["water", "repair"],
                    has_audio=True,
                )
            )
        )
        created_id = response["id"]
        assert response["status"] == "success"
        assert Path(api_server.RUNTIME_STATE_JSON).exists()
        stored_problem = next(problem for problem in api_server.PROBLEMS if problem["id"] == response["id"])
        assert stored_problem["village_address"] == "Near the school"
        assert stored_problem["visual_tags"] == ["water", "repair"]
        assert stored_problem["has_audio"] is True
    finally:
        if created_id:
            api_server.PROBLEMS[:] = [problem for problem in api_server.PROBLEMS if problem["id"] != created_id]
        api_server.RUNTIME_STATE_JSON = original_state_path


def test_update_volunteer_creates_normalized_record():
    try:
        response = asyncio.run(
            api_server.update_volunteer(
                {
                    "user_id": "new-volunteer",
                    "skills": ["Teaching"],
                    "availability_status": "available",
                }
            )
        )
        assert response["status"] == "success"
        assert response["data"]["id"] == "vol-new-volunteer"
        assert response["data"]["profiles"]["full_name"] == "Volunteer"
    finally:
        api_server.VOLUNTEERS[:] = [
            volunteer for volunteer in api_server.VOLUNTEERS if volunteer.get("user_id") != "new-volunteer"
        ]


@patch.object(api_server.recommender_service, "generate_recommendations")
def test_update_volunteer_triggers_live_rematch(mock_generate, tmp_path):
    original_people_csv = api_server.RUNTIME_PEOPLE_CSV
    api_server.RUNTIME_PEOPLE_CSV = str(tmp_path / "live_people.csv")

    volunteer = {
        "id": "VOL-TEST-001",
        "user_id": "mock-volunteer-uuid",
        "skills": ["Digital Literacy"],
        "availability_status": "available",
        "availability": "available",
        "home_location": "Sundarpur",
        "profiles": {
            "id": "mock-volunteer-uuid",
            "full_name": "Test Volunteer",
            "role": "volunteer",
        },
    }
    other_volunteer = {
        "id": "VOL-TEST-002",
        "user_id": "other-volunteer-uuid",
        "skills": ["Agriculture"],
        "availability_status": "available",
        "availability": "available",
        "home_location": "Sundarpur",
        "profiles": {
            "id": "other-volunteer-uuid",
            "full_name": "Agri Volunteer",
            "role": "volunteer",
        },
    }
    problem = {
        "id": "problem-rematch",
        "title": "Need farm support",
        "description": "Agriculture field assistance needed",
        "category": "agriculture",
        "village_name": "Sundarpur",
        "status": "in_progress",
        "matches": [{
            "id": "old-match",
            "problem_id": "problem-rematch",
            "volunteer_id": "VOL-TEST-001",
            "assigned_at": "2026-01-01T10:00:00",
            "completed_at": None,
            "notes": "Old assignment",
            "volunteers": volunteer,
        }],
        "created_at": "2026-01-01T09:00:00",
        "updated_at": "2026-01-01T10:00:00",
        "visual_tags": [],
    }

    api_server.VOLUNTEERS.extend([volunteer, other_volunteer])
    api_server.PROBLEMS.append(problem)

    mock_generate.return_value = {
        "severity_detected": "NORMAL",
        "severity_source": "auto",
        "proposal_location": "Sundarpur",
        "teams": [{
            "team_ids": "VOL-TEST-002",
            "team_names": "Agri Volunteer",
            "members": [{"person_id": "VOL-TEST-002", "skills": ["Agriculture"]}],
        }],
    }

    try:
        response = asyncio.run(
            api_server.update_volunteer(
                {
                    "id": "VOL-TEST-001",
                    "user_id": "mock-volunteer-uuid",
                    "skills": ["Agriculture"],
                    "availability_status": "available",
                    "full_name": "Test Volunteer",
                }
            )
        )
        assert response["status"] == "success"
        assert response["rematched_problems"] >= 1
        assert Path(api_server.RUNTIME_PEOPLE_CSV).exists()
        roster_text = Path(api_server.RUNTIME_PEOPLE_CSV).read_text(encoding="utf-8")
        assert "Agriculture" in roster_text
        assert problem["matches"]
        assert problem["matches"][0]["volunteer_id"] == "VOL-TEST-002"
        assert problem["matches"][0]["notes"].startswith("Auto-rematched after volunteer profile update")
        assert problem["status"] == "in_progress"
    finally:
        api_server.RUNTIME_PEOPLE_CSV = original_people_csv
        api_server.PROBLEMS[:] = [item for item in api_server.PROBLEMS if item.get("id") != "problem-rematch"]
        api_server.VOLUNTEERS[:] = [
            item for item in api_server.VOLUNTEERS
            if item.get("id") not in {"VOL-TEST-001", "VOL-TEST-002"}
        ]


def test_profile_upsert_and_media_upload_persist(tmp_path):
    original_state_path = api_server.RUNTIME_STATE_JSON
    original_media_root = api_server.MEDIA_ROOT
    api_server.RUNTIME_STATE_JSON = str(tmp_path / "app_state.json")
    api_server.MEDIA_ROOT = tmp_path / "media"
    api_server.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    problem_id = None
    try:
        profile_response = asyncio.run(
            api_server.upsert_profile(
                api_server.ProfileRequest(
                    full_name="Village Reporter",
                    phone="9999999999",
                    role="villager",
                    village_name="Sundarpur",
                )
            )
        )
        profile_id = profile_response["profile"]["id"]
        assert profile_response["status"] == "success"
        assert profile_response["profile"]["village_name"] == "Sundarpur"

        submit_response = asyncio.run(
            api_server.submit_problem_endpoint(
                api_server.ProblemRequest(
                    title="Broken drain",
                    description="Needs repair",
                    category="infrastructure",
                    village_name="Sundarpur",
                    village_address="Near the market",
                    villager_id=profile_id,
                    visual_tags=["drain"],
                )
            )
        )
        problem_id = submit_response["id"]

        media_response = asyncio.run(
            api_server.upload_media(
                file=UploadFile(filename="photo.jpg", file=io.BytesIO(b"photo-bytes")),
                kind="problem_photo",
                problem_id=problem_id,
            )
        )
        media_id = media_response["media"]["id"]
        stored_problem = next(problem for problem in api_server.PROBLEMS if problem["id"] == problem_id)
        assert media_id in stored_problem["media_ids"]
        assert stored_problem["media_ids"]
        assert media_response["media"]["url"].startswith("/media/")
    finally:
        if problem_id:
            api_server.PROBLEMS[:] = [problem for problem in api_server.PROBLEMS if problem["id"] != problem_id]
        api_server.RUNTIME_STATE_JSON = original_state_path
        api_server.MEDIA_ROOT = original_media_root
        api_server.PROFILES[:] = [profile for profile in api_server.PROFILES if profile.get("full_name") != "Village Reporter"]


def test_get_missing_volunteer_raises_not_found():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(api_server.get_volunteer("missing-volunteer"))
    assert exc_info.value.status_code == 404


def test_assign_task_is_idempotent_and_tasks_follow_problem_status():
    problem = {
        "id": "problem-dedup",
        "title": "Need electrician",
        "description": "Repair street light",
        "category": "infrastructure",
        "village_name": "Test Village",
        "status": "pending",
        "matches": [],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T10:00:00",
    }
    volunteer = {
        "id": "vol-dedup",
        "user_id": "user-dedup",
        "skills": ["Electrical Work"],
        "availability_status": "available",
        "profiles": {"full_name": "Electrician Alice"},
    }
    api_server.PROBLEMS.append(problem)
    api_server.VOLUNTEERS.append(volunteer)
    try:
        first = asyncio.run(api_server.assign_task("problem-dedup", {"volunteer_id": "vol-dedup"}))
        second = asyncio.run(api_server.assign_task("problem-dedup", {"volunteer_id": "vol-dedup"}))
        assert first["match"]["id"] == second["match"]["id"]

        asyncio.run(api_server.update_problem_status("problem-dedup", {"status": "completed"}))
        tasks = asyncio.run(api_server.get_volunteer_tasks("user-dedup"))
        assert tasks[0]["status"] == "completed"
    finally:
        api_server.PROBLEMS.remove(problem)
        api_server.VOLUNTEERS.remove(volunteer)
