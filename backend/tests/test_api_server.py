import asyncio
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile
from fastapi.exceptions import HTTPException

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_server


def test_health_endpoint():
    assert asyncio.run(api_server.health()) == {"status": "ok"}


@patch("api_server.train_model")
def test_train_endpoint(mock_train):
    mock_train.return_value = 0.85
    request = api_server.TrainRequest(out="test_model.pkl")
    response = api_server.train_endpoint(request)
    assert response.status == "ok"
    assert response.auc == 0.85


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
    mock_transcribe.return_value = "Transcribed text"
    upload = UploadFile(filename="sample.mp3", file=io.BytesIO(b"audio"))
    response = api_server.transcribe_endpoint(upload)
    assert response["text"] == "Transcribed text"


@patch("api_server.analyze_image")
def test_analyze_image_endpoint(mock_analyze):
    mock_analyze.return_value = {"top_label": "Infrastructure", "confidence": 0.9}
    upload = UploadFile(filename="sample.jpg", file=io.BytesIO(b"image"))
    response = api_server.analyze_image_endpoint(upload)
    assert response["top_label"] == "Infrastructure"


def test_submit_problem_writes_csv(tmp_path):
    original_csv = api_server.DEFAULT_PROPOSALS_CSV
    api_server.DEFAULT_PROPOSALS_CSV = str(tmp_path / "proposals.csv")
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
        assert Path(api_server.DEFAULT_PROPOSALS_CSV).exists()
        stored_problem = next(problem for problem in api_server.PROBLEMS if problem["id"] == response["id"])
        assert stored_problem["village_address"] == "Near the school"
        assert stored_problem["visual_tags"] == ["water", "repair"]
        assert stored_problem["has_audio"] is True
    finally:
        if created_id:
            api_server.PROBLEMS[:] = [problem for problem in api_server.PROBLEMS if problem["id"] != created_id]
        api_server.DEFAULT_PROPOSALS_CSV = original_csv


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
        assert len(problem["matches"]) == 1

        asyncio.run(api_server.update_problem_status("problem-dedup", {"status": "completed"}))
        tasks = asyncio.run(api_server.get_volunteer_tasks("user-dedup"))
        assert tasks[0]["status"] == "completed"
        assert problem["matches"][0]["completed_at"] is not None
    finally:
        api_server.PROBLEMS.remove(problem)
        api_server.VOLUNTEERS.remove(volunteer)
