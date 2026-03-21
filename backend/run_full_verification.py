import math
import wave
from pathlib import Path

from fastapi.testclient import TestClient

import api_server
from generate_canonical_dataset import main as generate_canonical_dataset
from m3_trainer import TrainingConfig, train_model
from recommender_service import RecommenderService
from utils import read_csv_norm


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_audio_fixture(path: Path) -> None:
    sample_rate = 16_000
    duration_seconds = 1.5
    amplitude = 12_000
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for index in range(int(sample_rate * duration_seconds)):
            envelope = 0.35 if index < sample_rate * 0.4 else 0.18
            sample = int(
                amplitude
                * envelope
                * (
                    math.sin(2 * math.pi * 440 * index / sample_rate)
                    + 0.3 * math.sin(2 * math.pi * 660 * index / sample_rate)
                )
            )
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        handle.writeframes(bytes(frames))


def verify_dataset() -> None:
    proposals = read_csv_norm(api_server.DEFAULT_PROPOSALS_CSV)
    people = read_csv_norm(api_server.DEFAULT_PEOPLE_CSV)
    pairs = read_csv_norm(api_server.DEFAULT_PAIRS_CSV)
    _assert(len(proposals) >= 6, "Expected at least 6 canonical proposals")
    _assert(len(people) >= 8, "Expected at least 8 canonical volunteers")
    _assert(len(pairs) == len(proposals) * len(people), "Pairs must cover every proposal-volunteer combination")
    _assert(any(row.get("label") == "1" for row in pairs), "Pairs must include positive labels")
    _assert(any(row.get("label") == "0" for row in pairs), "Pairs must include negative labels")


def verify_recommender(model_path: str) -> None:
    service = RecommenderService(
        model_path=model_path,
        people_csv=api_server.DEFAULT_PEOPLE_CSV,
        dataset_root=str(api_server.PATHS.data_dir),
    )
    base_request = {
        "proposal_text": "Urgent broken handpump near the primary school in Sundarpur needs repair support.",
        "village_name": "Sundarpur",
        "task_start": "2026-03-19T10:00:00",
        "task_end": "2026-03-19T12:00:00",
        "team_size": 1,
        "num_teams": 2,
        "auto_extract": True,
        "schedule_csv": api_server.DEFAULT_PEOPLE_CSV.replace("people.csv", "schedule.csv"),
    }
    without_overlap = dict(base_request, schedule_csv=None)
    with_overlap = dict(base_request)

    baseline = service.generate_recommendations(without_overlap)
    filtered = service.generate_recommendations(with_overlap)

    _assert(baseline["teams"], "Expected baseline recommendation teams")
    baseline_members = {member["person_id"] for team in baseline["teams"] for member in team["members"]}
    filtered_members = {member["person_id"] for team in filtered["teams"] for member in team["members"]}
    _assert("VOL-002" in baseline_members, "Expected seeded handpump expert in baseline recommendations")
    _assert("VOL-002" not in filtered_members, "Schedule filtering should exclude overlapping volunteer VOL-002")
    _assert(len(filtered["teams"]) <= 2, "num_teams limit must be enforced")


def verify_api_endpoints(model_path: str) -> None:
    client = TestClient(api_server.app)
    api_server.recommender_service.set_model_path(model_path)
    payload = {
        "proposal_text": "Need digital literacy support in Nirmalgaon for SHG bookkeeping.",
        "task_start": "2026-03-22T10:00:00",
        "task_end": "2026-03-22T12:00:00",
        "village_name": "Nirmalgaon",
        "model_path": model_path,
        "people_csv": api_server.DEFAULT_PEOPLE_CSV,
        "schedule_csv": str((api_server.PATHS.data_dir / "schedule.csv").resolve()),
        "num_teams": 2,
        "team_size": 2,
        "auto_extract": True,
    }
    recommend_response = client.post("/recommend", json=payload)
    _assert(recommend_response.status_code == 200, f"/recommend failed: {recommend_response.text}")
    recommend_data = recommend_response.json()
    _assert(recommend_data["teams"], "API recommend endpoint returned no teams")

    image_path = api_server.PATHS.data_dir / "test_image.ppm"
    with image_path.open("rb") as image_handle:
        image_response = client.post(
            "/analyze-image",
            files={"file": ("test_image.ppm", image_handle, "image/x-portable-pixmap")},
            data={"labels": "broken pump,road repair,digital literacy"},
        )
    _assert(image_response.status_code == 200, f"/analyze-image failed: {image_response.text}")
    image_data = image_response.json()
    _assert(bool(image_data.get("top_label")), "Image analysis did not return a top label")
    _assert(isinstance(image_data.get("tags"), list), "Image analysis did not return tags list")

    audio_path = api_server.PATHS.data_dir / "test_audio.wav"
    if not audio_path.exists():
        _write_audio_fixture(audio_path)
    with audio_path.open("rb") as audio_handle:
        audio_response = client.post(
            "/transcribe",
            files={"file": ("test_audio.wav", audio_handle, "audio/wav")},
        )
    _assert(audio_response.status_code == 200, f"/transcribe failed: {audio_response.text}")
    audio_data = audio_response.json()
    _assert(isinstance(audio_data.get("text"), str), "Transcription endpoint did not return string text")


def main() -> None:
    generate_canonical_dataset()
    api_server.reset_runtime_state()
    verify_dataset()

    model_path = str((api_server.PATHS.runtime_dir / "canonical_model.pkl").resolve())
    auc = train_model(
        TrainingConfig(
            proposals=api_server.DEFAULT_PROPOSALS_CSV,
            people=api_server.DEFAULT_PEOPLE_CSV,
            pairs=api_server.DEFAULT_PAIRS_CSV,
            out=model_path,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            village_locations=api_server.DEFAULT_VILLAGE_LOCATIONS,
            village_distances=api_server.DEFAULT_DISTANCE_CSV,
        )
    )
    _assert(0.0 <= auc <= 1.0, "Training AUC must be within [0, 1]")
    verify_recommender(model_path)
    verify_api_endpoints(model_path)
    print("Full backend verification passed.")


if __name__ == "__main__":
    main()
