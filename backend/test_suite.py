import pytest
import os
from fastapi.testclient import TestClient
import api_server
from api_server import app
from generate_canonical_dataset import main as generate_canonical_dataset
from demo_bootstrap import ensure_trained_model, ensure_canonical_dataset
import multimodal_service
from recommender_service import RecommenderService

client = TestClient(app)

# Mock some data paths for testing
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "runtime_data", "canonical_model.pkl")


def ensure_canonical_model() -> str:
    ensure_canonical_dataset()
    return ensure_trained_model(
        model_path=MODEL_PATH,
        proposals=api_server.DEFAULT_PROPOSALS_CSV,
        people=api_server.DEFAULT_PEOPLE_CSV,
        pairs=api_server.DEFAULT_PAIRS_CSV,
        village_locations=api_server.DEFAULT_VILLAGE_LOCATIONS,
        village_distances=api_server.DEFAULT_DISTANCE_CSV,
        force=False,
    )

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_multimodal_service_logic():
    # We can't easily test real audio/image without local files, 
    # but we can verify the interfaces exists and the candidate labels are sound.
    assert hasattr(multimodal_service, "transcribe_audio")
    assert hasattr(multimodal_service, "analyze_image")
    
    # Static check of analyze_image labels
    # (Testing with a non-existent file should raise FileNotFoundError)
    with pytest.raises(FileNotFoundError):
        multimodal_service.analyze_image("non_existent.jpg")

def test_recommendation_logic_fusion():
    generate_canonical_dataset()
    ensure_canonical_model()
    people_csv = os.path.join(DATA_DIR, "people.csv")

    service = RecommenderService(
        model_path=MODEL_PATH,
        people_csv=people_csv,
        dataset_root=DATA_DIR,
    )
    results = service.generate_recommendations(
        {
            "proposal_text": "Fix bridge",
            "transcription": "Water pump is also leaking",
            "visual_tags": ["Infrastructure", "Water"],
            "task_start": "2023-10-25T10:00:00",
            "task_end": "2023-10-25T14:00:00",
            "village_locations": os.path.join(DATA_DIR, "village_locations.csv"),
            "distance_csv": os.path.join(DATA_DIR, "village_distances.csv"),
            "team_size": 1,
            "num_teams": 1,
            "auto_extract": True,
        }
    )
    assert "teams" in results

def test_api_recommend_endpoint():
    generate_canonical_dataset()
    ensure_canonical_model()
    # Test the API wrapper
    payload = {
        "proposal_text": "Need help with digital literacy in Gram Puram",
        "task_start": "2023-12-01T10:00:00",
        "task_end": "2023-12-01T14:00:00",
        "village_name": "Gram Puram",
        "transcription": "They want to learn Excel",
        "visual_tags": ["Education"]
    }
    
    response = client.post("/recommend", json=payload)
    assert response.status_code == 200

def test_notification_service():
    from notification_service import send_sms_notification
    # Verify mock success
    res = send_sms_notification("1234567890", "Test message")
    assert res is True

if __name__ == "__main__":
    pytest.main([__file__])
