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


@patch("api_server.find_duplicate_problem_candidates")
@patch("api_server.suggest_immediate_problem_actions")
def test_problem_guidance_endpoint(mock_guidance, mock_duplicates):
    mock_duplicates.return_value = []
    mock_guidance.return_value = {
        "topic": "water",
        "summary": "Keep the joint stable.",
        "what_you_can_do_now": ["Lower flow", "Wrap externally"],
        "materials_to_find": ["cloth"],
        "safety_notes": ["Do not open live parts"],
        "when_to_stop": ["If pressure rises"],
        "best_duration": "Temporary only",
        "confidence": 0.83,
        "source": "gemini",
        "visual_tags": ["handpump"],
    }
    response = asyncio.run(
        api_server.problem_guidance_endpoint(
            api_server.ProblemGuidanceRequest(
                title="Broken handpump",
                description="Water leaking at the joint",
                category="water-sanitation",
                visual_tags=["handpump"],
            )
        )
    )
    assert response.topic == "water"
    assert response.what_you_can_do_now[0] == "Lower flow"
    assert mock_guidance.called


@patch.object(api_server, "find_duplicate_problem_candidates")
def test_submit_problem_attaches_duplicate_report(mock_duplicates, tmp_path):
    original_state_path = api_server.RUNTIME_STATE_JSON
    api_server.RUNTIME_STATE_JSON = str(tmp_path / "app_state.json")
    target_problem = {
        "id": "problem-duplicate-target",
        "title": "Broken handpump",
        "description": "The pump is leaking near the base",
        "category": "water-sanitation",
        "village_name": "Sundarpur",
        "status": "pending",
        "matches": [],
        "media_ids": [],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T10:00:00",
        "visual_tags": ["handpump"],
    }
    api_server.PROBLEMS.append(target_problem)
    mock_duplicates.return_value = [{
        "problem_id": target_problem["id"],
        "title": target_problem["title"],
        "village_name": target_problem["village_name"],
        "category": target_problem["category"],
        "status": target_problem["status"],
        "created_at": target_problem["created_at"],
        "distance_km": 0.0,
        "score": 0.93,
        "semantic_score": 0.91,
        "reason": "same village, same water topic",
        "suggested_action": "Attach to this case instead of opening a new one.",
    }]
    try:
        response = asyncio.run(
            api_server.submit_problem_endpoint(
                api_server.ProblemRequest(
                    title="Broken handpump",
                    description="Same pump leaking again",
                    category="water-sanitation",
                    village_name="Sundarpur",
                    village_address="Near the school",
                    reporter_name="Resident",
                    reporter_phone="9999999999",
                    visual_tags=["handpump"],
                )
            )
        )
        assert response["status"] == "duplicate_attached"
        assert response["id"] == target_problem["id"]
        assert response["duplicate_of"] == target_problem["id"]
        assert target_problem["duplicate_reports"]
        assert target_problem["duplicate_reports"][0]["duplicate_score"] == 0.93
    finally:
        api_server.PROBLEMS[:] = [problem for problem in api_server.PROBLEMS if problem["id"] != target_problem["id"]]
        api_server.RUNTIME_STATE_JSON = original_state_path
        api_server.reset_runtime_state()


def test_problem_timeline_endpoint_includes_case_history(tmp_path):
    original_state_path = api_server.RUNTIME_STATE_JSON
    original_media_root = api_server.MEDIA_ROOT
    api_server.RUNTIME_STATE_JSON = str(tmp_path / "app_state.json")
    api_server.MEDIA_ROOT = tmp_path / "media"
    api_server.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    problem = {
        "id": "problem-timeline",
        "title": "Leaking pipe",
        "description": "Pipe leaks near the road",
        "category": "water-sanitation",
        "village_name": "Sundarpur",
        "status": "in_progress",
        "matches": [{
            "id": "match-1",
            "problem_id": "problem-timeline",
            "volunteer_id": "VOL-001",
            "assigned_at": "2026-01-01T11:00:00",
            "completed_at": None,
            "notes": "Assigned for repair",
            "volunteers": {
                "id": "VOL-001",
                "user_id": "vol-001",
                "profiles": {"full_name": "Test Volunteer"},
            },
        }],
        "media_ids": [],
        "duplicate_reports": [{
            "id": "dup-1",
            "problem_id": "problem-timeline",
            "reported_at": "2026-01-01T12:00:00",
            "duplicate_reason": "same village, same topic",
            "title": "Leaking pipe",
        }],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T12:30:00",
        "visual_tags": ["pipe"],
    }
    api_server.PROBLEMS.append(problem)
    try:
        media = asyncio.run(
            api_server.upload_media(
                file=UploadFile(filename="photo.jpg", file=io.BytesIO(b"photo-bytes")),
                kind="problem_photo",
                problem_id=problem["id"],
            )
        )["media"]
        api_server._record_learning_event(
            "problem_edited",
            entity_type="problem",
            entity_id=problem["id"],
            summary="Edited problem problem-timeline",
            payload={"problem_id": problem["id"]},
            text="leaking pipe",
        )

        response = asyncio.run(api_server.problem_timeline_endpoint(problem["id"]))
        assert response["problem_id"] == problem["id"]
        event_types = [item["type"] for item in response["timeline"]]
        assert "reported" in event_types
        assert "duplicate_reported" in event_types
        assert "media_uploaded" in event_types
        assert "assigned" in event_types
        assert any(item["type"] == "problem_edited" for item in response["timeline"])
        assert response["summary"]["duplicate_count"] == 1
        assert media["id"] in response["problem"]["media_ids"]
    finally:
        api_server.PROBLEMS[:] = [item for item in api_server.PROBLEMS if item.get("id") != problem["id"]]
        api_server.MEDIA_ASSETS[:] = [item for item in api_server.MEDIA_ASSETS if item.get("problem_id") != problem["id"]]
        api_server.RUNTIME_STATE_JSON = original_state_path
        api_server.MEDIA_ROOT = original_media_root
        api_server.reset_runtime_state()


def test_weekly_briefing_endpoint_returns_root_cause_graph():
    response = asyncio.run(api_server.insights_briefing_endpoint(7))
    assert response["window_days"] == 7
    assert "root_cause_graph" in response
    assert "summary" in response["root_cause_graph"]
    assert isinstance(response["highlights"], list)


def test_public_status_board_endpoint_returns_summary():
    response = asyncio.run(api_server.public_status_board_endpoint(days_back=30))
    assert response["window_days"] == 30
    assert "items" in response
    assert "total_count" in response


@patch.object(api_server.DATA_STORE, "list_playbooks")
@patch.object(api_server.DATA_STORE, "list_inventory")
@patch("api_server._volunteer_reputation")
@patch("api_server._route_optimizer")
def test_operations_endpoints_return_data(mock_routes, mock_reputation, mock_inventory, mock_playbooks):
    mock_playbooks.return_value = [{
        "id": "playbook-1",
        "topic": "water",
        "village_name": "Sundarpur",
        "data": {
            "id": "playbook-1",
            "topic": "water",
            "title": "Handpump fix",
            "summary": "Temporary seal",
            "materials": ["tube"],
            "safety_notes": ["Keep pressure low"],
            "steps": ["Step 1"],
            "created_at": "2026-01-01T00:00:00",
        },
        "updated_at": "2026-01-01T00:00:00",
    }]
    mock_inventory.return_value = [{
        "id": "inv-1",
        "owner_type": "village",
        "owner_id": "Sundarpur",
        "item_name": "rubber tube",
        "quantity": 4,
        "data": {"notes": "Stored in the panchayat room"},
        "updated_at": "2026-01-01T00:00:00",
    }]
    mock_reputation.return_value = [{
        "volunteer_id": "vol-1",
        "name": "Alice",
        "home_location": "Sundarpur",
        "skills": ["plumbing"],
        "completed_count": 3,
        "open_assignments": 1,
        "duplicate_reports_seen": 0,
        "avg_resolution_hours": 12.5,
        "reliability_score": 0.88,
    }]
    mock_routes.return_value = [{
        "route_id": "route-1",
        "village_name": "Sundarpur",
        "problem_ids": ["prob-1"],
        "titles": ["Leaking pipe"],
        "problem_count": 1,
        "severity_counts": {"HIGH": 1},
        "recommended_volunteers": [{"volunteer_id": "vol-1", "name": "Alice", "skills": ["plumbing"]}],
        "route_hint": "Cluster this village's open cases into one visit where possible.",
    }]

    playbooks = asyncio.run(api_server.playbooks_endpoint())
    inventory = asyncio.run(api_server.inventory_list_endpoint())
    assert playbooks[0]["title"] == "Handpump fix"
    assert inventory[0]["item_name"] == "rubber tube"
    assert asyncio.run(api_server.reputation_endpoint())["volunteers"][0]["name"] == "Alice"
    assert asyncio.run(api_server.route_optimizer_endpoint())["routes"][0]["route_id"] == "route-1"


@patch("api_server.build_seasonal_risk_forecast")
@patch("api_server.build_preventive_maintenance_plan")
@patch("api_server.build_hotspot_heatmap")
@patch("api_server.build_campaign_mode_plan")
def test_planning_endpoints_return_data(mock_campaign, mock_heatmap, mock_maintenance, mock_seasonal):
    mock_seasonal.return_value = {
        "generated_at": "2026-01-01T00:00:00",
        "window_days": 365,
        "summary": "Seasonal forecast",
        "risks": [{"risk_id": "risk-1", "topic": "water"}],
        "top_topics": [("water", 2)],
        "top_months": [("2026-01", 2)],
    }
    mock_maintenance.return_value = {
        "generated_at": "2026-01-01T00:00:00",
        "window_days": 180,
        "summary": "Maintenance plan",
        "items": [{"plan_id": "maint-1", "village_name": "Sundarpur", "asset_type": "water-system"}],
        "top_assets": [("water-system", 2)],
    }
    mock_heatmap.return_value = {
        "generated_at": "2026-01-01T00:00:00",
        "window_days": 90,
        "summary": "Heatmap",
        "cells": [{"cell_id": "heat-1", "village_name": "Sundarpur"}],
    }
    mock_campaign.return_value = {
        "generated_at": "2026-01-01T00:00:00",
        "window_days": 30,
        "summary": "Campaign plan",
        "campaigns": [{"campaign_id": "campaign-water", "target_villages": ["Sundarpur"]}],
        "top_topics": [("water", 3)],
    }

    assert asyncio.run(api_server.seasonal_risk_endpoint())["risks"][0]["topic"] == "water"
    assert asyncio.run(api_server.maintenance_plan_endpoint())["items"][0]["asset_type"] == "water-system"
    assert asyncio.run(api_server.hotspot_heatmap_endpoint())["cells"][0]["cell_id"] == "heat-1"
    assert asyncio.run(api_server.campaign_mode_endpoint())["campaigns"][0]["campaign_id"] == "campaign-water"


def test_evidence_comparison_endpoint_returns_proof_details():
    problem = {
        "id": "problem-evidence",
        "title": "Broken handpump",
        "description": "Handpump leak",
        "category": "infrastructure",
        "village_name": "Sundarpur",
        "status": "completed",
        "matches": [],
        "media_ids": [],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T12:00:00",
        "visual_tags": ["handpump"],
        "proof": {
            "before_media_id": "before-1",
            "after_media_id": "after-1",
            "verification": {
                "accepted": True,
                "confidence": 0.93,
                "summary": "The after image shows the pump repaired.",
                "detected_change": "seal repaired",
                "source": "stored-proof",
            },
        },
    }
    api_server.PROBLEMS.append(problem)
    with patch.object(api_server, "_asset_by_id") as mock_asset:
        mock_asset.side_effect = [
            {"id": "before-1", "url": "/media/before.jpg"},
            {"id": "after-1", "url": "/media/after.jpg"},
        ]
        try:
            response = asyncio.run(api_server.evidence_comparison_endpoint(problem["id"]))
            assert response["accepted"] is True
            assert response["before_url"] == "/media/before.jpg"
            assert response["after_url"] == "/media/after.jpg"
            assert response["detected_change"] == "seal repaired"
        finally:
            api_server.PROBLEMS[:] = [item for item in api_server.PROBLEMS if item.get("id") != problem["id"]]


@patch.object(api_server.DATA_STORE, "record_followup_feedback")
def test_follow_up_feedback_endpoint_records_and_reopens(mock_record, tmp_path):
    problem = {
        "id": "problem-followup",
        "title": "Leaking pipe",
        "description": "Pipe leaks near the road",
        "category": "water-sanitation",
        "village_name": "Sundarpur",
        "status": "completed",
        "matches": [],
        "media_ids": [],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T12:00:00",
        "visual_tags": ["pipe"],
    }
    api_server.PROBLEMS.append(problem)
    mock_record.return_value = {
        "id": "fb-1",
        "problem_id": problem["id"],
        "source": "public-board",
        "response": "still_broken",
    }
    try:
        response = asyncio.run(
            api_server.problem_follow_up_feedback_endpoint(
                problem["id"],
                api_server.FollowUpFeedbackRequest(response="still_broken", source="public-board"),
            )
        )
        assert response["status"] == "success"
        assert response["problem"]["status"] == "in_progress"
        assert response["feedback"]["response"] == "still_broken"
    finally:
        api_server.PROBLEMS[:] = [item for item in api_server.PROBLEMS if item.get("id") != problem["id"]]


@patch("api_server.suggest_jugaad_fix")
def test_jugaad_assist_endpoint(mock_suggest, tmp_path):
    original_state_path = api_server.RUNTIME_STATE_JSON
    original_media_root = api_server.MEDIA_ROOT
    api_server.RUNTIME_STATE_JSON = str(tmp_path / "app_state.json")
    api_server.MEDIA_ROOT = tmp_path / "media"
    api_server.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    problem = {
        "id": "problem-jugaad",
        "title": "Broken handpump",
        "description": "Pump is leaking at the joint",
        "category": "infrastructure",
        "village_name": "Sundarpur",
        "status": "in_progress",
        "matches": [],
        "media_ids": [],
        "created_at": "2026-01-01T10:00:00",
        "updated_at": "2026-01-01T10:00:00",
        "visual_tags": ["handpump"],
    }
    api_server.PROBLEMS.append(problem)
    try:
        broken_media = asyncio.run(
            api_server.upload_media(
                file=UploadFile(filename="broken.jpg", file=io.BytesIO(b"broken-bytes")),
                kind="jugaad_broken",
                problem_id=problem["id"],
                volunteer_id="mock-volunteer-uuid",
            )
        )["media"]
        materials_media = asyncio.run(
            api_server.upload_media(
                file=UploadFile(filename="materials.jpg", file=io.BytesIO(b"materials-bytes")),
                kind="jugaad_materials",
                problem_id=problem["id"],
                volunteer_id="mock-volunteer-uuid",
            )
        )["media"]

        mock_suggest.return_value = {
            "summary": "Use the tube as a temporary seal around the leak.",
            "problem_read": "A cracked handpump joint with spare wire and tube available.",
            "observed_broken_part": "handpump joint",
            "observed_materials": "rubber tube and wire",
            "temporary_fix": "Wrap the joint externally and secure it gently.",
            "step_by_step": ["Shut off water", "Dry the joint", "Wrap with tube", "Secure with wire"],
            "safety_notes": ["Keep pressure low"],
            "materials_to_use": ["rubber tube", "wire"],
            "materials_to_avoid": ["sharp metal"],
            "when_to_stop": ["If the leak worsens"],
            "needs_official_part": True,
            "confidence": 0.84,
            "source": "gemini",
            "broken_analysis": {"top_label": "handpump", "confidence": 0.9, "tags": ["handpump"]},
            "materials_analysis": {"top_label": "rubber tube", "confidence": 0.9, "tags": ["rubber tube", "wire"]},
        }

        response = asyncio.run(
            api_server.jugaad_assist_endpoint(
                api_server.JugaadRequest(
                    problem_id=problem["id"],
                    broken_media_id=broken_media["id"],
                    materials_media_id=materials_media["id"],
                    volunteer_id="mock-volunteer-uuid",
                )
            )
        )
        assert response.problem_id == problem["id"]
        assert response.summary.startswith("Use the tube")
        assert response.needs_official_part is True
        assert mock_suggest.called
    finally:
        api_server.PROBLEMS[:] = [item for item in api_server.PROBLEMS if item.get("id") != problem["id"]]
        api_server.MEDIA_ASSETS[:] = [item for item in api_server.MEDIA_ASSETS if item.get("problem_id") != problem["id"]]
        api_server.RUNTIME_STATE_JSON = original_state_path
        api_server.MEDIA_ROOT = original_media_root
        api_server.reset_runtime_state()


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
        api_server.reset_runtime_state()


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
        api_server.reset_runtime_state()


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
        stored_state = api_server.DATA_STORE.load_runtime_state()
        stored_problem = next(problem for problem in stored_state.problems if problem["id"] == response["id"])
        assert stored_problem["village_address"] == "Near the school"
        assert stored_problem["visual_tags"] == ["water", "repair"]
        assert stored_problem["has_audio"] is True
        assert api_server.DATA_STORE.get_meta("state_version") is not None
        learning_events = api_server.DATA_STORE.get_recent_learning_events(limit=5, event_type="problem_reported")
        assert any(event["entity_id"] == created_id for event in learning_events)
    finally:
        if created_id:
            api_server.PROBLEMS[:] = [problem for problem in api_server.PROBLEMS if problem["id"] != created_id]
        api_server.RUNTIME_STATE_JSON = original_state_path
        api_server.reset_runtime_state()


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
        api_server.reset_runtime_state()


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
        assert "Agriculture" in str(response["data"].get("skills", ""))
        runtime_state = api_server.DATA_STORE.load_runtime_state()
        assert any(volunteer.get("user_id") == "mock-volunteer-uuid" for volunteer in runtime_state.volunteers)
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
        api_server.reset_runtime_state()


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
        api_server.reset_runtime_state()


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
        api_server.reset_runtime_state()
