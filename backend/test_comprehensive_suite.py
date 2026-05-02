from __future__ import annotations

import io
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import api_server
from insights_service import (
    analyze_coordinator_query,
    build_campaign_mode_plan,
    build_hotspot_heatmap,
    build_insight_overview,
    build_preventive_maintenance_plan,
    build_root_cause_graph,
    build_seasonal_risk_forecast,
    build_weekly_briefing,
    find_duplicate_problem_candidates,
    infer_problem_triage,
)
from multimodal_service import suggest_immediate_problem_actions


class FakeStore:
    def __init__(self) -> None:
        self.meta: dict[str, object] = {"state_version": 0}
        self.learning_events: list[dict[str, object]] = []
        self.playbooks: list[dict[str, object]] = []
        self.inventory: list[dict[str, object]] = []
        self.feedback: list[dict[str, object]] = []
        self.runtime_state = SimpleNamespace(problems=[], volunteers=[], profiles=[], media_assets=[])

    def ensure_schema(self) -> None:
        return None

    def ensure_seed_catalog(self, force: bool = False) -> None:
        return None

    def clear_runtime_state(self) -> None:
        self.runtime_state = SimpleNamespace(problems=[], volunteers=[], profiles=[], media_assets=[])

    def save_runtime_state(self, *, problems, volunteers, profiles, media_assets) -> None:
        self.runtime_state = SimpleNamespace(
            problems=list(problems),
            volunteers=list(volunteers),
            profiles=list(profiles),
            media_assets=list(media_assets),
        )

    def load_runtime_state(self):
        return self.runtime_state

    def load_seed_rows(self, dataset: str):
        return []

    def has_runtime_data(self) -> bool:
        state = self.runtime_state
        return bool(state.problems or state.volunteers or state.profiles or state.media_assets)

    def get_village_coordinates(self):
        return {
            "Sundarpur": (21.1458, 79.0882),
            "Nirmalgaon": (20.7453, 78.6022),
            "Lakshmipur": (23.2, 77.0833),
            "Devnagar": (23.2599, 77.4126),
            "Riverbend": (21.2514, 81.6296),
        }

    def get_village_name_rows(self):
        return [
            {"village_name": "Sundarpur", "district": "Nagpur Rural", "state": "Maharashtra", "lat": 21.1458, "lng": 79.0882},
            {"village_name": "Nirmalgaon", "district": "Wardha", "state": "Maharashtra", "lat": 20.7453, "lng": 78.6022},
            {"village_name": "Lakshmipur", "district": "Sehore", "state": "Madhya Pradesh", "lat": 23.2, "lng": 77.0833},
            {"village_name": "Devnagar", "district": "Bhopal Rural", "state": "Madhya Pradesh", "lat": 23.2599, "lng": 77.4126},
            {"village_name": "Riverbend", "district": "Raipur", "state": "Chhattisgarh", "lat": 21.2514, "lng": 81.6296},
        ]

    def get_village_names(self):
        return [row["village_name"] for row in self.get_village_name_rows()]

    def get_people_rows(self):
        return [
            {
                "person_id": "vol-1",
                "id": "vol-1",
                "name": "Skilled Sam",
                "skills": "Plumbing;Masonry",
                "home_location": "Sundarpur",
                "availability": "available",
            }
        ]

    def get_distance_lookup(self):
        return {}

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)

    def set_meta(self, key, value):
        self.meta[key] = value

    def record_learning_event(self, *, event_type, entity_type=None, entity_id=None, summary=None, payload=None, text=None):
        event = {
            "id": f"evt-{len(self.learning_events) + 1}",
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "summary": summary,
            "data": payload or {},
            "created_at": "2026-01-01T00:00:00",
        }
        self.learning_events.append(event)
        return event

    def get_recent_learning_events(self, *, limit=50, event_type=None, entity_type=None, entity_id=None):
        rows = list(self.learning_events)
        if event_type:
            rows = [row for row in rows if row.get("event_type") == event_type]
        if entity_type:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if entity_id:
            rows = [row for row in rows if row.get("entity_id") == entity_id]
        return rows[-max(1, int(limit)) :]

    def upsert_inventory_item(self, *, owner_type, owner_id, item_name, quantity, data=None):
        payload = {
            "id": f"inv-{len(self.inventory) + 1}",
            "owner_type": owner_type,
            "owner_id": owner_id,
            "item_name": item_name,
            "quantity": int(quantity),
            "data": data or {},
            "updated_at": "2026-01-01T00:00:00",
        }
        self.inventory = [
            row for row in self.inventory
            if not (row["owner_type"] == owner_type and row["owner_id"] == owner_id and row["item_name"] == item_name)
        ]
        self.inventory.append(payload)
        return payload

    def list_inventory(self, *, owner_type=None, owner_id=None):
        rows = list(self.inventory)
        if owner_type:
            rows = [row for row in rows if row["owner_type"] == owner_type]
        if owner_id:
            rows = [row for row in rows if row["owner_id"] == owner_id]
        return rows

    def save_playbook(self, *, playbook_id, topic, village_name, data):
        payload = {
            "id": playbook_id,
            "topic": topic,
            "village_name": village_name,
            "data": data,
            "updated_at": "2026-01-01T00:00:00",
        }
        self.playbooks = [row for row in self.playbooks if row["id"] != playbook_id]
        self.playbooks.append(payload)
        return payload

    def list_playbooks(self, *, topic=None, village_name=None, limit=25):
        rows = list(self.playbooks)
        if topic:
            rows = [row for row in rows if row.get("topic") == topic]
        if village_name:
            rows = [row for row in rows if row.get("village_name") == village_name]
        return rows[: max(1, int(limit))]

    def record_followup_feedback(self, *, problem_id, source, response, data=None):
        payload = {
            "id": f"fb-{len(self.feedback) + 1}",
            "problem_id": problem_id,
            "source": source,
            "response": response,
            "data": data or {},
        }
        self.feedback.append(payload)
        return payload


def _make_problem(problem_id: str, title: str, village_name: str, category: str, status: str = "pending", **extra):
    created_at = extra.get("created_at", datetime.now().replace(microsecond=0).isoformat())
    return {
        "id": problem_id,
        "title": title,
        "description": extra.get("description") or title,
        "category": category,
        "village_name": village_name,
        "village_address": extra.get("village_address"),
        "status": status,
        "severity": extra.get("severity", "NORMAL"),
        "severity_source": extra.get("severity_source", "auto"),
        "lat": extra.get("lat", 21.1458),
        "lng": extra.get("lng", 79.0882),
        "created_at": created_at,
        "updated_at": extra.get("updated_at", created_at),
        "visual_tags": list(extra.get("visual_tags") or []),
        "matches": list(extra.get("matches") or []),
        "duplicate_reports": list(extra.get("duplicate_reports") or []),
        "media_ids": list(extra.get("media_ids") or []),
        "profiles": extra.get("profiles") or {
            "id": "resident-1",
            "full_name": "Reporter",
            "phone": "9999999999",
            "role": "villager",
            "created_at": created_at,
        },
        "proof": extra.get("proof"),
    }


def _seed_runtime(monkeypatch, tmp_path):
    fake_store = FakeStore()
    monkeypatch.setattr(api_server, "DATA_STORE", fake_store)
    monkeypatch.setattr(api_server.recommender_service, "_store", fake_store, raising=False)
    monkeypatch.setattr(api_server, "RUNTIME_STATE_JSON", str(tmp_path / "app_state.json"))
    monkeypatch.setattr(api_server, "RUNTIME_PEOPLE_CSV", str(tmp_path / "live_people.csv"))
    monkeypatch.setattr(api_server, "MEDIA_ROOT", tmp_path / "media")
    monkeypatch.setattr(api_server, "STATE_VERSION", 0)
    api_server.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    api_server.PROBLEMS[:] = [
        _make_problem("problem-water-1", "Broken handpump", "Sundarpur", "water-sanitation", visual_tags=["handpump", "water"]),
        _make_problem("problem-health-1", "Fever cluster", "Nirmalgaon", "health-nutrition", visual_tags=["fever", "mosquito"], severity="HIGH"),
        _make_problem("problem-road-1", "Road potholes", "Lakshmipur", "infrastructure", visual_tags=["road", "pothole"]),
    ]
    api_server.VOLUNTEERS[:] = [
        {
            "id": "vol-1",
            "user_id": "vol-1",
            "skills": ["Plumbing", "Masonry"],
            "availability_status": "available",
            "availability": "available",
            "home_location": "Sundarpur",
            "created_at": "2026-01-01T09:00:00",
            "updated_at": "2026-01-01T09:00:00",
            "profiles": {
                "id": "vol-1",
                "full_name": "Skilled Sam",
                "email": "sam@example.com",
                "phone": "1111111111",
                "role": "volunteer",
                "created_at": "2026-01-01T09:00:00",
            },
        },
        {
            "id": "vol-2",
            "user_id": "vol-2",
            "skills": ["Health outreach"],
            "availability_status": "available",
            "availability": "available",
            "home_location": "Nirmalgaon",
            "created_at": "2026-01-01T09:00:00",
            "updated_at": "2026-01-01T09:00:00",
            "profiles": {
                "id": "vol-2",
                "full_name": "Health Hina",
                "email": "hina@example.com",
                "phone": "2222222222",
                "role": "volunteer",
                "created_at": "2026-01-01T09:00:00",
            },
        },
    ]
    api_server.PROFILES[:] = [
        {
            "id": "resident-1",
            "full_name": "Reporter",
            "email": "resident@example.com",
            "phone": "9999999999",
            "role": "villager",
            "created_at": "2026-01-01T09:00:00",
        },
        api_server.VOLUNTEERS[0]["profiles"],
        api_server.VOLUNTEERS[1]["profiles"],
    ]
    api_server.MEDIA_ASSETS[:] = []
    api_server.VILLAGE_COORDS_CACHE.clear()
    api_server.VILLAGE_COORDS_CACHE.update(fake_store.get_village_coordinates())
    return fake_store


def test_backend_heuristics_cover_duplicate_triage_and_planning():
    problems = [
        _make_problem("dup-1", "Handpump leakage", "Sundarpur", "water-sanitation", status="pending", visual_tags=["handpump", "leak"]),
        _make_problem("dup-2", "Mosquito fever complaints", "Nirmalgaon", "health-nutrition", status="in_progress", visual_tags=["fever", "mosquito"]),
        _make_problem("dup-3", "Solar inverter failure", "Riverbend", "infrastructure", status="pending", visual_tags=["solar", "inverter"]),
    ]

    triage = infer_problem_triage(
        problem_title="Broken handpump in Sundarpur",
        problem_description="The pump is leaking and villagers have no water",
        category="water-sanitation",
        visual_tags=["handpump", "water"],
        severity="HIGH",
    )
    assert triage["topic"] == "water"
    assert triage["urgency"] in {"immediate", "same-day"}
    assert triage["response_path"]

    duplicates = find_duplicate_problem_candidates(
        problems,
        title="Leaking pump in Sundarpur",
        description="Same handpump keeps leaking near the school",
        village_name="Sundarpur",
        category="water-sanitation",
        visual_tags=["handpump", "leak"],
        limit=3,
    )
    assert duplicates
    assert duplicates[0]["problem_id"] == "dup-1"

    overview = build_insight_overview(problems, [
        {"id": "vol-1", "profiles": {"full_name": "Skilled Sam"}, "skills": ["Plumbing"]},
        {"id": "vol-2", "profiles": {"full_name": "Health Hina"}, "skills": ["Health outreach"]},
    ], days_back=30)
    assert overview["stats"]["problem_count"] >= 3

    briefing = build_weekly_briefing(problems, [], days_back=7)
    assert briefing["summary"]
    assert briefing["root_cause_graph"]["summary"]

    root_graph = build_root_cause_graph(problems, days_back=30)
    assert root_graph["summary"]
    assert root_graph["nodes"]

    seasonal = build_seasonal_risk_forecast(problems, days_back=365)
    assert seasonal["summary"]

    maintenance = build_preventive_maintenance_plan(problems, [], days_back=180)
    assert maintenance["items"]

    heatmap = build_hotspot_heatmap(problems, days_back=90)
    assert heatmap["cells"]

    campaign = build_campaign_mode_plan(problems, [], days_back=30)
    assert campaign["campaigns"]

    chat = analyze_coordinator_query(
        "Which villages have the most water issues this month?",
        problems=problems,
        volunteers=[],
        days_back=30,
        limit=5,
    )
    assert chat["answer"]
    assert chat["overview"]["stats"]["problem_count"] >= 3

    action = suggest_immediate_problem_actions(
        problem_title="Broken handpump",
        problem_description="No water is flowing",
        category="water-sanitation",
        visual_tags=["handpump", "water"],
    )
    assert action["what_you_can_do_now"]
    assert action["materials_to_find"]


def test_backend_http_feature_surface(tmp_path, monkeypatch):
    fake_store = _seed_runtime(monkeypatch, tmp_path)
    client = TestClient(api_server.app)

    monkeypatch.setattr(
        api_server,
        "find_duplicate_problem_candidates",
        lambda *args, **kwargs: [
            {
                "problem_id": "problem-water-1",
                "title": "Broken handpump",
                "village_name": "Sundarpur",
                "category": "water-sanitation",
                "status": "pending",
                "created_at": "2026-01-01T10:00:00",
                "distance_km": 0.0,
                "score": 0.97,
                "semantic_score": 0.94,
                "reason": "same village, same water topic",
                "suggested_action": "Attach to this case instead of opening a new one.",
            }
        ],
    )
    monkeypatch.setattr(
        api_server,
        "suggest_immediate_problem_actions",
        lambda **kwargs: {
            "topic": "water",
            "department": "Public works / water",
            "urgency": "same-day",
            "response_path": "Route to public works and keep a volunteer watch.",
            "summary": "Use a temporary wrap to keep water flowing.",
            "what_you_can_do_now": ["Lower pressure", "Wrap the leak"],
            "materials_to_find": ["cloth", "tape"],
            "safety_notes": ["Keep clear of pressurized fittings"],
            "when_to_stop": ["If the crack widens"],
            "best_duration": "Temporary only",
            "confidence": 0.87,
            "source": "fallback",
            "visual_tags": ["handpump"],
        },
    )
    monkeypatch.setattr(
        api_server,
        "verify_resolution_proof",
        lambda *args, **kwargs: {
            "accepted": True,
            "confidence": 0.91,
            "summary": "Before/after images show the pump has been repaired.",
            "detected_change": "Leak resolved",
            "source": "stubbed-verification",
        },
    )
    monkeypatch.setattr(
        api_server,
        "suggest_jugaad_fix",
        lambda *args, **kwargs: {
            "summary": "Temporary wire clamp plan",
            "problem_read": "Broken handpump with a loose fitting",
            "observed_broken_part": "handpump fitting",
            "observed_materials": "wire, bamboo, cloth",
            "temporary_fix": "Clamp the fitting and reduce pressure.",
            "step_by_step": ["Drain pressure", "Clamp loose joint", "Check for leaks"],
            "safety_notes": ["Do not use on cracked high-pressure sections"],
            "materials_to_use": ["wire", "cloth"],
            "materials_to_avoid": ["sharp metal"],
            "when_to_stop": ["If leakage increases"],
            "needs_official_part": True,
            "confidence": 0.88,
            "source": "stubbed-jugaad",
            "broken_analysis": {"top_label": "handpump", "confidence": 0.99},
            "materials_analysis": {"top_label": "wire", "confidence": 0.99},
        },
    )
    monkeypatch.setattr(api_server, "notify_team_assignment", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "notify_problem_resolved", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "notify_problem_follow_up", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_server.recommender_service,
        "generate_recommendations",
        lambda config: {
            "severity_detected": "HIGH",
            "severity_source": "auto",
            "proposal_location": config.get("village_name") or "Sundarpur",
            "teams": [
                {
                    "team_ids": "vol-1",
                    "team_names": "Skilled Sam",
                    "team_size": 1,
                    "goodness": 0.97,
                    "team_score": 0.97,
                    "coverage": 1.0,
                    "k_robustness": 0.9,
                    "redundancy": 0.05,
                    "set_size": 1.0,
                    "willingness_avg": 0.95,
                    "willingness_min": 0.95,
                    "avg_distance_km": 0.0,
                    "members": [
                        {
                            "person_id": "vol-1",
                            "name": "Skilled Sam",
                            "skills": ["Plumbing", "Masonry"],
                            "availability": "available",
                            "home_location": "Sundarpur",
                        }
                    ],
                }
            ],
        },
    )

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    profile_response = client.post("/profile", json={
        "full_name": "Supervisor Sita",
        "email": "sita@example.com",
        "phone": "3333333333",
        "role": "supervisor",
        "village_name": "Sundarpur",
    })
    assert profile_response.status_code == 200

    volunteer_response = client.post("/volunteer", json={
        "user_id": "vol-1",
        "full_name": "Skilled Sam",
        "skills": ["Plumbing", "Masonry"],
        "availability_status": "available",
        "home_location": "Sundarpur",
    })
    assert volunteer_response.status_code == 200
    assert volunteer_response.json()["data"]["user_id"] == "vol-1"

    guidance_response = client.post("/api/v1/problems/instant-guidance", json={
        "title": "Broken handpump near school",
        "description": "Same leak as yesterday and still no water",
        "category": "water-sanitation",
        "village_name": "Sundarpur",
        "severity": "HIGH",
        "visual_tags": ["handpump", "water"],
    })
    assert guidance_response.status_code == 200
    guidance_json = guidance_response.json()
    assert guidance_json["topic"] == "water"
    assert guidance_json["duplicate_candidates"]

    submit_response = client.post("/submit-problem", json={
        "title": "Broken handpump near school",
        "description": "Same leak as yesterday and still no water",
        "category": "water-sanitation",
        "village_name": "Sundarpur",
        "village_address": "Near the school",
        "reporter_name": "Resident A",
        "reporter_phone": "9999999999",
        "visual_tags": ["handpump", "water"],
    })
    assert submit_response.status_code == 200
    submit_json = submit_response.json()
    assert submit_json["status"] == "duplicate_attached"
    duplicate_problem_id = submit_json["duplicate_of"]

    duplicate_problem = next(problem for problem in api_server.PROBLEMS if problem["id"] == duplicate_problem_id)
    assert duplicate_problem["duplicate_reports"]

    proof_before = client.post(
        "/media",
        files={"file": ("before.jpg", io.BytesIO(b"before"), "image/jpeg")},
        data={"kind": "problem_photo", "problem_id": duplicate_problem_id},
    )
    proof_after = client.post(
        "/media",
        files={"file": ("after.jpg", io.BytesIO(b"after"), "image/jpeg")},
        data={"kind": "problem_photo", "problem_id": duplicate_problem_id},
    )
    assert proof_before.status_code == 200
    assert proof_after.status_code == 200
    before_id = proof_before.json()["media"]["id"]
    after_id = proof_after.json()["media"]["id"]

    proof_response = client.post(
        f"/problems/{duplicate_problem_id}/proof",
        json={
            "volunteer_id": "vol-1",
            "before_media_id": before_id,
            "after_media_id": after_id,
            "notes": "Repaired using a temporary clamp",
        },
    )
    assert proof_response.status_code == 200
    proof_json = proof_response.json()
    assert proof_json["problem"]["status"] == "completed"
    assert proof_json["proof"]["verification"]["accepted"] is True

    evidence_response = client.get(f"/api/v1/problems/{duplicate_problem_id}/evidence-comparison")
    assert evidence_response.status_code == 200
    assert evidence_response.json()["summary"]

    timeline_response = client.get(f"/api/v1/problems/{duplicate_problem_id}/timeline")
    assert timeline_response.status_code == 200
    timeline_json = timeline_response.json()
    assert timeline_json["summary"]["duplicate_count"] >= 1
    assert any(item["type"] == "media_uploaded" for item in timeline_json["timeline"])

    dashboard_response = client.post("/api/v1/jugaad/assist", json={
        "problem_id": duplicate_problem_id,
        "broken_media_id": before_id,
        "materials_media_id": after_id,
        "volunteer_id": "vol-1",
        "notes": "wire, bamboo, cloth",
    })
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["temporary_fix"]

    followup_response = client.post(f"/problems/{duplicate_problem_id}/follow-up-feedback", json={
        "source": "public-board",
        "response": "resolved",
        "note": "Working now",
    })
    assert followup_response.status_code == 200
    assert followup_response.json()["feedback"]["response"] == "resolved"

    recommendation = client.post("/recommend", json={
        "proposal_text": "Fix the handpump in Sundarpur",
        "task_start": "2026-01-01T10:00:00",
        "task_end": "2026-01-01T12:00:00",
        "village_name": "Sundarpur",
        "num_teams": 1,
        "team_size": 1,
    })
    assert recommendation.status_code == 200
    assert recommendation.json()["teams"]

    insights_chat = client.post("/api/v1/insights/chat", json={
        "query": "Which villages have the most water issues?",
        "days_back": 30,
        "limit": 5,
    })
    assert insights_chat.status_code == 200
    assert insights_chat.json()["answer"]

    overview = client.get("/api/v1/insights/overview?days_back=30")
    assert overview.status_code == 200
    assert overview.json()["stats"]["problem_count"] >= 3

    briefing = client.get("/api/v1/insights/briefing?days_back=7")
    assert briefing.status_code == 200
    assert briefing.json()["root_cause_graph"]["summary"]

    playbooks = client.get("/api/v1/playbooks?limit=5")
    assert playbooks.status_code == 200
    assert playbooks.json()

    inventory_add = client.post("/api/v1/inventory", json={
        "owner_type": "village",
        "owner_id": "Sundarpur",
        "item_name": "pipe seal tape",
        "quantity": 2,
        "notes": "kept with the volunteer team",
    })
    assert inventory_add.status_code == 200
    inventory = client.get("/api/v1/inventory?owner_type=village&owner_id=Sundarpur")
    assert inventory.status_code == 200
    assert inventory.json()[0]["item_name"] == "pipe seal tape"

    escalations = client.get("/api/v1/escalations?days_back=30")
    assert escalations.status_code == 200
    escalations_json = escalations.json()
    assert escalations_json["generated_at"]
    assert escalations_json["window_days"] == 30

    reputation = client.get("/api/v1/reputation?days_back=90")
    assert reputation.status_code == 200
    assert reputation.json()["volunteers"]

    routes = client.get("/api/v1/routes/optimizer?days_back=14")
    assert routes.status_code == 200
    assert routes.json()["routes"]

    seasonal = client.get("/api/v1/insights/seasonal-risk?days_back=365")
    assert seasonal.status_code == 200
    seasonal_json = seasonal.json()
    assert seasonal_json["summary"]
    assert seasonal_json["generated_at"]

    maintenance = client.get("/api/v1/maintenance/plan?days_back=180")
    assert maintenance.status_code == 200
    assert maintenance.json()["items"]

    heatmap = client.get("/api/v1/hotspots/heatmap?days_back=90")
    assert heatmap.status_code == 200
    assert heatmap.json()["cells"]

    campaign = client.get("/api/v1/campaigns/plan?days_back=30")
    assert campaign.status_code == 200
    assert campaign.json()["campaigns"]

    status_board = client.get("/api/v1/public/status-board?days_back=60")
    assert status_board.status_code == 200
    assert status_board.json()["total_count"] >= 1

    events = client.get("/api/v1/learning/events?limit=20")
    assert events.status_code == 200
    assert events.json()["events"]

    state_version = client.get("/state-version")
    assert state_version.status_code == 200
    assert state_version.json()["version"] >= 1
