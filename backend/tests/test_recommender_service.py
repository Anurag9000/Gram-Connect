import os
import pickle
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recommender_service import RecommenderService


def test_service_skips_missing_model(tmp_path):
    people_csv = tmp_path / "people.csv"
    people_csv.write_text(
        "person_id,name,text,willingness_eff,willingness_bias\n"
        "p1,Alice,water quality assessment,0.8,0.7\n",
        encoding="utf-8",
    )

    service = RecommenderService(
        model_path=str(tmp_path / "missing.pkl"),
        people_csv=str(people_csv),
        dataset_root=str(tmp_path),
    )

    assert service.model_bundle is None


def test_service_generates_recommendations_without_model(tmp_path):
    people_csv = tmp_path / "people.csv"
    people_csv.write_text(
        "person_id,name,text,willingness_eff,willingness_bias,availability,home_location\n"
        "p1,Alice,water quality assessment; handpump repair,0.8,0.7,immediately available,Village A\n"
        "p2,Bob,public health outreach; community planning,0.7,0.6,generally available,Village B\n",
        encoding="utf-8",
    )

    service = RecommenderService(
        model_path=str(tmp_path / "missing.pkl"),
        people_csv=str(people_csv),
        dataset_root=str(tmp_path),
    )

    result = service.generate_recommendations(
        {
            "proposal_text": "Urgent handpump repair needed in Village A",
            "task_start": "2026-01-01T10:00:00",
            "task_end": "2026-01-01T12:00:00",
            "auto_extract": True,
            "team_size": 1,
            "num_teams": 1,
        }
    )

    assert result["severity_detected"] == "HIGH"
    assert result["teams"]
    assert result["teams"][0]["members"][0]["person_id"] == "p1"
