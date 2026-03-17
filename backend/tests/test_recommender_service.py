import os
import pickle
import sys
from pathlib import Path
from unittest.mock import patch

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


@patch("recommender_service.run_recommender")
def test_service_passes_optional_fields_to_core(mock_run, tmp_path):
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
    mock_run.return_value = {
        "severity_detected": "NORMAL",
        "severity_source": "auto",
        "proposal_location": "Village Z",
        "teams": [],
    }

    service.generate_recommendations(
        {
            "proposal_text": "Need help in Village Z",
            "village_name": "Village Z",
            "task_start": "2026-01-01T10:00:00",
            "task_end": "2026-01-01T12:00:00",
            "team_size": 2,
            "num_teams": 4,
            "size_buckets": "small:1-2:4",
            "schedule_csv": "/tmp/schedule.csv",
            "distance_scale": 25,
            "distance_decay": 12,
            "overwork_penalty": 0.3,
            "lambda_red": 1.2,
            "lambda_size": 0.8,
            "lambda_will": 0.9,
            "topk_swap": 7,
        }
    )

    cfg = mock_run.call_args.args[0]
    assert cfg.proposal_location_override == "Village Z"
    assert cfg.team_size == 2
    assert cfg.num_teams == 4
    assert cfg.size_buckets == "small:1-2:4"
    assert cfg.schedule_csv == "/tmp/schedule.csv"
    assert cfg.distance_scale == 25
    assert cfg.distance_decay == 12
    assert cfg.overwork_penalty == 0.3
    assert cfg.lambda_red == 1.2
    assert cfg.lambda_size == 0.8
    assert cfg.lambda_will == 0.9
    assert cfg.topk_swap == 7
