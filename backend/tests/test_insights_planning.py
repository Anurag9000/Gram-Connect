import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import insights_service


def _sample_problem(problem_id, title, description, category, village_name, status="pending"):
    now = datetime.now().isoformat()
    return {
        "id": problem_id,
        "title": title,
        "description": description,
        "category": category,
        "village_name": village_name,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "visual_tags": [category],
        "matches": [],
    }


def test_seasonal_risk_forecast_detects_recurring_topic():
    problems = [
        _sample_problem("p1", "Broken handpump", "Water leak", "water", "Sundarpur"),
        _sample_problem("p2", "Contaminated water", "Water smells bad", "water", "Sundarpur"),
        _sample_problem("p3", "Fever cluster", "People are sick", "health", "Nirmalgaon"),
        _sample_problem("p4", "Fever and cough", "Health alert", "health", "Nirmalgaon"),
    ]

    result = insights_service.build_seasonal_risk_forecast(problems, days_back=365)

    assert result["risks"]
    assert any(item["topic"] in {"water", "health"} for item in result["risks"])
    assert result["top_topics"]


def test_preventive_maintenance_plan_groups_assets_by_village():
    problems = [
        _sample_problem("p1", "Broken handpump", "Water leak", "water", "Sundarpur"),
        _sample_problem("p2", "Handpump pressure low", "Water issue", "water", "Sundarpur"),
        _sample_problem("p3", "Road crack", "Pothole near school", "infrastructure", "Nirmalgaon"),
        _sample_problem("p4", "Road crack 2", "Pothole near market", "infrastructure", "Nirmalgaon"),
    ]
    volunteers = [
        {"id": "vol-1", "user_id": "vol-1", "skills": ["plumbing"], "home_location": "Sundarpur", "profiles": {"full_name": "Alice"}},
        {"id": "vol-2", "user_id": "vol-2", "skills": ["masonry"], "home_location": "Nirmalgaon", "profiles": {"full_name": "Bob"}},
    ]

    result = insights_service.build_preventive_maintenance_plan(problems, volunteers, days_back=180)

    assert result["items"]
    assert any(item["village_name"] == "Sundarpur" for item in result["items"])
    assert any(item["asset_type"] for item in result["items"])


def test_hotspot_heatmap_returns_cells():
    problems = [
        _sample_problem("p1", "Broken handpump", "Water leak", "water", "Sundarpur"),
        _sample_problem("p2", "Handpump pressure low", "Water issue", "water", "Sundarpur"),
        _sample_problem("p3", "Road crack", "Pothole near school", "infrastructure", "Nirmalgaon"),
    ]

    result = insights_service.build_hotspot_heatmap(problems, days_back=90)

    assert result["cells"]
    assert result["cells"][0]["village_name"] in {"Sundarpur", "Nirmalgaon"}


def test_campaign_mode_plan_proposes_target_villages():
    problems = [
        _sample_problem("p1", "Broken handpump", "Water leak", "water", "Sundarpur"),
        _sample_problem("p2", "Contaminated water", "Water issue", "water", "Sundarpur"),
        _sample_problem("p3", "Contaminated water", "Water issue", "water", "Devnagar"),
    ]
    volunteers = [
        {"id": "vol-1", "user_id": "vol-1", "skills": ["handpump repair and maintenance"], "home_location": "Sundarpur", "profiles": {"full_name": "Alice"}},
        {"id": "vol-2", "user_id": "vol-2", "skills": ["masonry"], "home_location": "Devnagar", "profiles": {"full_name": "Bob"}},
    ]

    result = insights_service.build_campaign_mode_plan(problems, volunteers, days_back=30)

    assert result["campaigns"]
    assert result["campaigns"][0]["target_villages"]
    assert result["campaigns"][0]["problem_count"] >= 1
