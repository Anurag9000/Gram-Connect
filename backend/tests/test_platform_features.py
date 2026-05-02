from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_server
import platform_service as platform_service_module
from platform_service import (
    answer_policy_question,
    assess_burnout_signals,
    assess_proof_spoofing,
    build_broadcast_feed,
    autofill_problem_form,
    build_ab_test_plan,
    build_anomaly_dashboard,
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
    build_repeat_breakdown_metrics,
    build_resident_feedback_summary,
    build_shift_plan,
    build_skill_certifications,
    build_suggestion_box,
    build_training_mode,
    build_village_champions,
    build_webhook_events,
    build_work_order_templates,
    find_case_similarity_explorer,
)


class FakePlatformStore:
    def __init__(self) -> None:
        self.platform_records: list[dict[str, object]] = []
        self.learning_events: list[dict[str, object]] = []
        self.followup_feedback: list[dict[str, object]] = []

    def get_village_name_rows(self):
        return [
            {"village_name": "Sundarpur", "district": "Nagpur Rural", "state": "Maharashtra"},
            {"village_name": "Nirmalgaon", "district": "Wardha", "state": "Maharashtra"},
        ]

    def list_platform_records(self, *, record_type: str, subtype=None, owner_id=None, limit: int = 50):
        rows = [row for row in self.platform_records if row["record_type"] == record_type]
        if subtype is not None:
            rows = [row for row in rows if row.get("subtype") == subtype]
        if owner_id is not None:
            rows = [row for row in rows if row.get("owner_id") == owner_id]
        return rows[: max(1, int(limit))]

    def upsert_platform_record(self, *, record_type, record_id, subtype=None, owner_id=None, status=None, data=None):
        payload = {
            "id": record_id,
            "record_type": record_type,
            "subtype": subtype,
            "owner_id": owner_id,
            "status": status,
            "data": data or {},
            "updated_at": "2026-01-01T00:00:00",
        }
        self.platform_records = [row for row in self.platform_records if row["id"] != record_id]
        self.platform_records.append(payload)
        return payload

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

    def set_meta(self, key, value):
        return None

    def get_recent_learning_events(self, *, limit=50, event_type=None, entity_type=None, entity_id=None):
        rows = list(self.learning_events)
        if event_type is not None:
            rows = [row for row in rows if row.get("event_type") == event_type]
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if entity_id is not None:
            rows = [row for row in rows if row.get("entity_id") == entity_id]
        return rows[-max(1, int(limit)) :]

    def list_followup_feedback(self, *, limit: int = 100, problem_id=None, source=None, response=None):
        rows = list(self.followup_feedback)
        if problem_id is not None:
            rows = [row for row in rows if row.get("problem_id") == problem_id]
        if source is not None:
            rows = [row for row in rows if row.get("source") == source]
        if response is not None:
            rows = [row for row in rows if row.get("response") == response]
        return rows[: max(1, int(limit))]

    def save_runtime_state(self, **kwargs):
        return None

    def clear_runtime_state(self):
        return None


def _seed_runtime():
    api_server.PROBLEMS[:] = [
        {
            "id": "problem-water-1",
            "title": "Leaking handpump",
            "description": "Water leaking around the base",
            "category": "water-sanitation",
            "village_name": "Sundarpur",
            "status": "pending",
            "created_at": "2026-01-01T08:00:00",
            "updated_at": "2026-01-01T08:00:00",
            "visual_tags": ["handpump", "water"],
            "proof": {
                "before_media_id": "media-before",
                "after_media_id": "media-after",
                "verification": {
                    "accepted": True,
                    "confidence": 0.92,
                    "summary": "Stable repair",
                    "detected_change": "seal tightened",
                    "source": "stored-proof",
                },
            },
        },
        {
            "id": "problem-health-1",
            "title": "Fever cluster",
            "description": "Several residents reporting fever",
            "category": "health-nutrition",
            "village_name": "Nirmalgaon",
            "status": "completed",
            "created_at": "2026-01-02T08:00:00",
            "updated_at": "2026-01-03T08:00:00",
            "visual_tags": ["fever", "mosquito"],
        },
        {
            "id": "problem-water-2",
            "title": "Pump jammed again",
            "description": "Same water point keeps failing",
            "category": "water-sanitation",
            "village_name": "Sundarpur",
            "status": "pending",
            "created_at": "2026-01-04T08:00:00",
            "updated_at": "2026-01-04T08:00:00",
            "visual_tags": ["pump"],
        },
    ]
    api_server.VOLUNTEERS[:] = [
        {
            "id": "vol-1",
            "user_id": "vol-1",
            "skills": ["Plumbing", "Masonry"],
            "availability_status": "available",
            "home_location": "Sundarpur",
            "profiles": {"id": "vol-1", "full_name": "Skilled Sam", "role": "volunteer", "phone": "1111111111"},
        },
        {
            "id": "vol-2",
            "user_id": "vol-2",
            "skills": ["Health outreach"],
            "availability_status": "busy",
            "home_location": "Nirmalgaon",
            "profiles": {"id": "vol-2", "full_name": "Helper Hema", "role": "volunteer", "phone": "2222222222"},
        },
    ]


def test_platform_service_builders_cover_core_features(monkeypatch):
    monkeypatch.setattr(
        platform_service_module,
        "find_duplicate_problem_candidates",
        lambda *args, **kwargs: [{"problem_id": "problem-2", "title": "Pump jammed again"}],
    )
    problems = list(api_server.PROBLEMS)
    volunteers = list(api_server.VOLUNTEERS)

    assets = build_asset_registry(problems, days_back=365)
    procurement = build_procurement_tracker(problems, days_back=365)
    hierarchy = build_district_hierarchy(problems, api_server.DATA_STORE.get_village_name_rows(), days_back=365)
    work_orders = build_work_order_templates()
    spoofing = assess_proof_spoofing({
        "id": "problem-spoof",
        "proof": {"before_media_id": "media-1", "after_media_id": "media-1"},
    })
    confirmation = build_resident_confirmation(problems[0])
    audit_pack = build_audit_pack(problems[0], [{"type": "reported"}], [{"event_type": "learning"}])
    certs = build_skill_certifications(volunteers, problems)
    shifts = build_shift_plan(volunteers, problems)
    training = build_training_mode()
    burnout = assess_burnout_signals(volunteers, problems)
    suggestions = build_suggestion_box([{"id": "s-1", "text": "Fix the pump sooner"}])
    polls = build_community_polls([{"id": "p-1", "question": "Which repair first?"}])
    announcements = build_village_champions([{"id": "c-1", "name": "Village lead"}])
    impact = build_impact_measurement(problems)
    ab_tests = build_ab_test_plan(problems)
    anomalies = build_anomaly_dashboard(problems)
    budget = build_budget_forecast(problems)
    autofill = autofill_problem_form("Broken handpump leaking near the school", village_name="Sundarpur")
    similarity = find_case_similarity_explorer(problems[0], problems)
    memory = build_conversation_memory([
        {"id": "m-1", "owner_id": "coord-1", "updated_at": "2026-01-03T00:00:00"},
        {"id": "m-2", "owner_id": "coord-1", "updated_at": "2026-01-04T00:00:00"},
    ], user_id="coord-1")
    policy = answer_policy_question("What should we do about privacy?")
    custom_forms = build_custom_forms_bundle([{"id": "f-1"}])
    webhooks = build_webhook_events([{"id": "w-1"}])
    export_bundle = build_bulk_export_bundle(problems, volunteers, [{"id": "asset-1", "record_type": "asset"}])
    broadcasts = build_broadcast_feed([
        {
            "id": "broadcast-1",
            "record_type": "broadcast",
            "subtype": "community_event",
            "owner_id": "coord-1",
            "status": "sent",
            "data": {
                "title": "Water camp",
                "message": "Camp starts on Saturday.",
                "event_type": "community_event",
                "audience_type": "villages",
                "target_villages": ["Sundarpur"],
                "tags": ["water camp"],
                "media_ids": [],
                "created_at": "2026-01-01T00:00:00",
            },
            "updated_at": "2026-01-01T00:00:00",
        }
    ], scope="villages", village_name="Sundarpur")
    feedback_summary = build_resident_feedback_summary(
        problems,
        [
                {
                    "id": "fb-1",
                    "problem_id": "problem-water-1",
                    "source": "public-board",
                    "response": "resolved",
                    "data": {
                        "volunteer_id": "vol-1",
                        "rating": 5,
                        "note": "Great work",
                    },
                    "created_at": "2026-04-04T00:00:00",
                },
            ],
            volunteers,
        )
    repeat_breakdown = build_repeat_breakdown_metrics(problems, days_back=365)

    assert assets["assets"]
    assert procurement["items"]
    assert hierarchy["districts"][0]["district"]
    assert work_orders[0]["steps"]
    assert spoofing["accepted"] is False
    assert confirmation["options"] == ["resolved", "still_broken", "needs_more_help"]
    assert audit_pack["problem"]["id"] == problems[0]["id"]
    assert certs[0]["badges"]
    assert shifts[0]["assigned_problem_ids"]
    assert len(training) == 3
    assert burnout[0]["signal"] in {"low", "medium", "high"}
    assert suggestions[0]["text"] == "Fix the pump sooner"
    assert polls[0]["question"] == "Which repair first?"
    assert announcements[0]["name"] == "Village lead"
    assert impact["closure_rate"] > 0
    assert ab_tests[0]["variant_b"] == "duplicate-aware dispatch"
    assert anomalies[0]["signal"] in {"spike", "cluster"}
    assert budget["total_estimated_budget"] >= 0
    assert autofill["category"] == "water-sanitation"
    assert similarity["matches"]
    assert memory["items"]
    assert "public views" in policy["answer"].lower()
    assert custom_forms[0]["id"] == "f-1"
    assert webhooks[0]["id"] == "w-1"
    assert export_bundle["problems"][0]["id"] == problems[0]["id"]
    assert broadcasts["items"][0]["title"] == "Water camp"
    assert feedback_summary["average_rating"] == 5
    assert feedback_summary["volunteers"][0]["volunteer_name"] in {"Skilled Sam", "vol-1"}
    assert repeat_breakdown["villages"][0]["village_name"] == "Sundarpur"


def test_platform_endpoints_store_and_export(monkeypatch, tmp_path):
    monkeypatch.setattr(
        platform_service_module,
        "find_duplicate_problem_candidates",
        lambda *args, **kwargs: [{"problem_id": "problem-water-2", "title": "Pump jammed again"}],
    )
    fake_store = FakePlatformStore()
    monkeypatch.setattr(api_server, "DATA_STORE", fake_store)
    monkeypatch.setattr(api_server, "RUNTIME_STATE_JSON", str(tmp_path / "app_state.json"))
    monkeypatch.setattr(api_server, "RUNTIME_PEOPLE_CSV", str(tmp_path / "live_people.csv"))
    monkeypatch.setattr(api_server, "MEDIA_ROOT", tmp_path / "media")
    api_server.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    _seed_runtime()
    fake_store.followup_feedback = [
        {
            "id": "fb-1",
            "problem_id": "problem-water-1",
            "source": "public-board",
            "response": "resolved",
            "data": {
                "volunteer_id": "vol-1",
                "rating": 5,
                "note": "Great work",
            },
            "created_at": "2026-04-04T00:00:00",
        }
    ]

    overview = asyncio.run(api_server.platform_overview_endpoint())
    assert overview["asset_registry"]["assets"]
    assert overview["record_counts"]["assets"] == 0
    assert "broadcasts" in overview["record_counts"]

    stored = asyncio.run(
        api_server.platform_records_upsert_endpoint(
            "asset",
            api_server.PlatformRecordRequest(
                record_id="asset-1",
                subtype="pump",
                owner_id="Sundarpur",
                status="healthy",
                data={"name": "Pump A"},
            ),
        )
    )
    assert stored["record_type"] == "asset"

    listed = asyncio.run(api_server.platform_records_list_endpoint("asset"))
    assert listed["items"][0]["id"] == "asset-1"

    broadcast = asyncio.run(
        api_server.create_broadcast_endpoint(
            api_server.BroadcastRequest(
                owner_id="coord-1",
                title="Water camp",
                message="Camp starts on Saturday.",
                event_type="community_event",
                audience_type="villages",
                target_villages=["Sundarpur"],
                tags=["water camp"],
            )
        )
    )
    assert broadcast["broadcast"]["title"] == "Water camp"

    broadcasts = asyncio.run(api_server.list_broadcasts_endpoint(audience="villages", village_name="Sundarpur", limit=10))
    assert broadcasts["items"][0]["title"] == "Water camp"

    feedback = asyncio.run(api_server.resident_feedback_analytics_endpoint())
    assert feedback["average_rating"] == 5
    assert feedback["volunteers"][0]["volunteer_name"] in {"Skilled Sam", "vol-1"}

    repeats = asyncio.run(api_server.repeat_breakdown_endpoint(days_back=365))
    assert repeats["villages"]

    confirmation = asyncio.run(
        api_server.resident_confirmation_endpoint(
            "problem-water-1",
            api_server.ResidentConfirmationRequest(
                response="resolved",
                source="public-board",
                note="Fixed and tested",
            ),
        )
    )
    assert confirmation["status"] == "success"
    assert confirmation["problem"]["status"] == "completed"

    audit_pack = asyncio.run(api_server.audit_pack_endpoint("problem-water-1"))
    assert audit_pack["problem"]["id"] == "problem-water-1"
    assert audit_pack["generated_at"]

    autofill = asyncio.run(api_server.form_autofill_endpoint(api_server.ProblemTextRequest(text="Broken handpump near school", village_name="Sundarpur")))
    assert autofill["category"] == "water-sanitation"

    similarity = asyncio.run(api_server.case_similarity_endpoint("problem-water-1"))
    assert similarity["matches"]

    policy = asyncio.run(api_server.policy_question_endpoint(api_server.PolicyQuestionRequest(question="How do we handle privacy?")))
    assert "public views" in policy["answer"].lower()

    export_bundle = asyncio.run(api_server.platform_export_endpoint())
    assert export_bundle["problems"]
    assert export_bundle["platform_records"]
    assert any(record["record_type"] == "broadcast" for record in export_bundle["platform_records"])
