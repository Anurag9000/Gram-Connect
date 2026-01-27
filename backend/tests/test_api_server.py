import pytest
from fastapi.testclient import TestClient
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_server import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch('api_server.train_model')
def test_train_endpoint(mock_train):
    mock_train.return_value = 0.85
    payload = {
        "out": "test_model.pkl"
    }
    response = client.post("/train", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["auc"] == 0.85

@patch('api_server.generate_recommendations')
@patch('api_server.notify_team_assignment')
def test_recommend_endpoint(mock_notify, mock_rec):
    mock_rec.return_value = {
        "severity_detected": "NORMAL",
        "severity_source": "auto",
        "proposal_location": "Village A",
        "teams": [{"team_ids": "p1", "members": []}]
    }
    
    payload = {
        "proposal_text": "Test proposal",
        "task_start": "2023-01-01T10:00:00",
        "task_end": "2023-01-01T12:00:00",
        "village_name": "Village A"
    }
    
    response = client.post("/recommend", json=payload)
    assert response.status_code == 200
    assert response.json()["severity_detected"] == "NORMAL"
    assert mock_notify.called

@patch('api_server.transcribe_audio')
def test_transcribe_endpoint(mock_trans):
    mock_trans.return_value = "Transcribed text"
    response = client.post("/transcribe?file_path=test.mp3")
    assert response.status_code == 200
    assert response.json()["text"] == "Transcribed text"

@patch('api_server.analyze_image')
def test_analyze_image_endpoint(mock_analyze):
    mock_analyze.return_value = {"top_label": "Infrastructure", "confidence": 0.9}
    response = client.post("/analyze-image?file_path=test.jpg")
    assert response.status_code == 200
    assert response.json()["top_label"] == "Infrastructure"
