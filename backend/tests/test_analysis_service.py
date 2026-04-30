import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import analysis_service


def test_chat_with_database_summarizes_water_trends_without_gemini():
    problems = [
        {
            "id": "p-1",
            "title": "Broken handpump",
            "description": "Water supply is down in Sundarpur.",
            "category": "water-sanitation",
            "village_name": "Sundarpur",
            "severity": "HIGH",
            "status": "pending",
            "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "visual_tags": ["water", "pump"],
            "matches": [],
        },
        {
            "id": "p-2",
            "title": "Water contamination",
            "description": "Residents report unsafe water in Sundarpur.",
            "category": "water-sanitation",
            "village_name": "Sundarpur",
            "severity": "HIGH",
            "status": "pending",
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "visual_tags": ["water", "contamination"],
            "matches": [],
        },
        {
            "id": "p-3",
            "title": "Road pothole",
            "description": "A road issue in another village.",
            "category": "infrastructure",
            "village_name": "Nirmalgaon",
            "severity": "NORMAL",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "visual_tags": ["road"],
            "matches": [],
        },
    ]
    volunteers = []

    with patch.object(analysis_service, "_has_gemini_key", return_value=False):
        answer = analysis_service.chat_with_database(
            "Which villages have had the most water-related issues this month?",
            json.dumps(problems),
            json.dumps(volunteers),
        )

    assert "Sundarpur" in answer
    assert "water" in answer.lower()


def test_chat_with_database_finds_idle_volunteer_without_gemini():
    problems = [
        {
            "id": "p-1",
            "title": "Old assignment",
            "description": "Masonry work completed long ago.",
            "category": "infrastructure",
            "village_name": "Nirmalgaon",
            "severity": "NORMAL",
            "status": "completed",
            "created_at": (datetime.now() - timedelta(days=20)).isoformat(),
            "matches": [
                {
                    "volunteer_id": "vol-1",
                    "assigned_at": (datetime.now() - timedelta(days=20)).isoformat(),
                }
            ],
        }
    ]
    volunteers = [
        {
            "id": "vol-1",
            "user_id": "vol-1",
            "skills": ["masonry", "construction"],
            "home_location": "Nirmalgaon",
            "availability_status": "available",
            "profiles": {"full_name": "Mason Meena"},
        }
    ]

    with patch.object(analysis_service, "_has_gemini_key", return_value=False):
        answer = analysis_service.chat_with_database(
            "Show me all volunteers in Nirmalgaon who know masonry but haven't been assigned anything in 2 weeks.",
            json.dumps(problems),
            json.dumps(volunteers),
        )

    assert "Mason Meena" in answer
    assert "days since last assignment" in answer


def test_cluster_problems_groups_related_pump_failures():
    problems = [
        {
            "id": "p-1",
            "title": "Broken pump",
            "description": "Handpump failed near the school.",
            "category": "water-sanitation",
            "village_name": "Sundarpur",
            "severity": "HIGH",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "lat": 21.1,
            "lng": 79.0,
            "visual_tags": ["pump", "water"],
        },
        {
            "id": "p-2",
            "title": "Pump not working",
            "description": "Another handpump failure in the same belt.",
            "category": "water-sanitation",
            "village_name": "Sundarpur",
            "severity": "HIGH",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "lat": 21.11,
            "lng": 79.01,
            "visual_tags": ["pump", "water"],
        },
        {
            "id": "p-3",
            "title": "Tree planting request",
            "description": "Different issue elsewhere.",
            "category": "environment",
            "village_name": "Lakshmipur",
            "severity": "LOW",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "lat": 23.2,
            "lng": 77.08,
            "visual_tags": ["tree"],
        },
    ]

    with patch.object(analysis_service, "_has_gemini_key", return_value=False), patch.object(
        analysis_service,
        "_dense_embeddings",
        return_value=(np.asarray([[1.0, 0.0], [0.98, 0.02], [0.0, 1.0]]), "test"),
    ):
        result = analysis_service.cluster_problems(json.dumps(problems))

    assert result["total_problems"] == 3
    assert result["clusters"]
    assert any(cluster["risk_type"] == "infrastructure" for cluster in result["clusters"])
    assert any("shared infrastructure fault" in cluster["recommendation"].lower() for cluster in result["clusters"])
