import asyncio
import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import UploadFile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multimodal_service
import api_server


@patch("multimodal_service._has_gemini_key", return_value=True)
@patch("multimodal_service._read_file_bytes", return_value=b"fake-audio")
@patch("os.path.exists", return_value=True)
@patch("multimodal_service.get_gemini_client")
def test_transcribe_audio_uses_gemini(mock_get_client, mock_exists, mock_read_bytes, mock_has_key):
    response = MagicMock()
    response.text = """
    {
      "text": "नाली जाम है",
      "language_code": "hi",
      "language_name": "Hindi",
      "source": "gemini"
    }
    """
    client = MagicMock()
    client.models.generate_content.return_value = response
    mock_get_client.return_value = client

    result = multimodal_service.transcribe_audio("sample.wav")

    assert result["text"] == "नाली जाम है"
    assert result["language"] == "hi"
    assert result["language_name"] == "Hindi"
    assert client.models.generate_content.called


@patch("multimodal_service._has_gemini_key", return_value=True)
@patch("multimodal_service._read_file_bytes", return_value=b"fake-image")
@patch("os.path.exists", return_value=True)
@patch("multimodal_service.get_gemini_client")
def test_analyze_image_uses_gemini(mock_get_client, mock_exists, mock_read_bytes, mock_has_key):
    response = MagicMock()
    response.text = """
    {
      "top_label": "digital literacy",
      "confidence": 0.88,
      "tags": ["digital literacy", "education"],
      "all_probs": {
        "digital literacy": 0.88,
        "education": 0.1
      }
    }
    """
    client = MagicMock()
    client.models.generate_content.return_value = response
    mock_get_client.return_value = client

    result = multimodal_service.analyze_image("sample.jpg", ["digital literacy", "education"])

    assert result["top_label"] == "digital literacy"
    assert result["confidence"] == 0.88
    assert result["tags"][0] == "digital literacy"
    assert result["all_probs"]["education"] == 0.1


@patch("multimodal_service._has_gemini_key", return_value=False)
@patch("os.path.exists")
@patch("PIL.Image.open")
def test_analyze_image_falls_back_to_clip(mock_img_open, mock_exists, mock_has_key):
    mock_exists.return_value = True
    mock_get_clip = MagicMock()
    mock_model = MagicMock()
    mock_preprocess = MagicMock()
    mock_get_clip.return_value = (mock_model, mock_preprocess)

    import torch

    mock_logits = torch.tensor([[10.0, 1.0]])
    mock_model.return_value = (mock_logits, None)
    mock_clip = MagicMock()
    mock_clip.tokenize.return_value = torch.zeros((2, 77))

    with patch("multimodal_service.get_clip", mock_get_clip), patch.dict("sys.modules", {"clip": mock_clip}):
        result = multimodal_service.analyze_image("fake.jpg", ["label1", "label2"])

    assert result["top_label"] == "label1"
    assert result["confidence"] > 0.9


@patch("multimodal_service._has_gemini_key", return_value=False)
@patch("multimodal_service.get_whisper")
@patch("os.path.exists")
def test_transcribe_audio_falls_back_to_whisper(mock_exists, mock_get_whisper, mock_has_key):
    mock_exists.return_value = True
    model = mock_get_whisper.return_value
    model.transcribe.return_value = {"text": " hello world "}

    result = multimodal_service.transcribe_audio("sample.mp3")

    assert result["text"] == "hello world"
    assert result["source"] == "whisper"
    assert result["language"] is None or result["language"] == "en"


@patch("multimodal_service._has_gemini_key", return_value=True)
@patch("multimodal_service._read_file_bytes", return_value=b"fake-image")
@patch("os.path.exists", return_value=True)
@patch("multimodal_service.get_gemini_client")
def test_verify_resolution_proof_uses_task_context_and_rejects_mismatch(mock_get_client, mock_exists, mock_read_bytes, mock_has_key):
    response = MagicMock()
    response.text = """
    {
      "accepted": false,
      "confidence": 0.08,
      "task_match": false,
      "same_scene": false,
      "issue_fixed": false,
      "summary": "The uploaded images depict a road pothole and do not match a digital literacy training task.",
      "detected_change": "task mismatch",
      "source": "gemini"
    }
    """
    client = MagicMock()
    client.models.generate_content.return_value = response
    mock_get_client.return_value = client

    result = multimodal_service.verify_resolution_proof(
        "before.jpg",
        "after.jpg",
        problem_title="Digital Literacy Camp",
        problem_description="Conduct digital literacy training for residents",
        category="education",
        visual_tags=["digital literacy"],
    )

    assert result["accepted"] is False
    assert result["task_match"] is False
    assert "do not match" in result["summary"]
    assert client.models.generate_content.called


@patch("multimodal_service._has_gemini_key", return_value=True)
@patch("multimodal_service._read_file_bytes", return_value=b"fake-image")
@patch("os.path.exists", return_value=True)
@patch("multimodal_service.get_gemini_client")
def test_generate_jugaad_fix_guidance_normalizes_scalar_fields(
    mock_get_client, mock_exists, mock_read_bytes, mock_has_key
):
    response = MagicMock()
    response.text = """
    {
      "source": "gemini",
      "confidence": "not-a-number",
      "situation_summary": "Temporary brace is feasible.",
      "materials_identified": "rubber tube, wire",
      "temporary_fix_steps": "Shut off water, brace the joint",
      "safety_warnings": ["Do not touch live wiring"],
      "when_to_stop": "Stop if the joint flexes.",
      "escalation": "Request the official replacement part."
    }
    """
    client = MagicMock()
    client.models.generate_content.return_value = response
    mock_get_client.return_value = client

    result = multimodal_service.generate_jugaad_fix_guidance(
        "broken.jpg",
        "materials.jpg",
        problem_title="Handpump joint failure",
        problem_description="The coupling is loose and leaking",
        category="infrastructure",
        village_name="Sundarpur",
        problem_id="prob-1",
    )

    assert result["source"] == "gemini"
    assert result["confidence"] == 0.0
    assert result["materials_identified"] == ["rubber tube", "wire"]
    assert result["temporary_fix_steps"] == ["Shut off water", "brace the joint"]
    assert result["safety_warnings"] == ["Do not touch live wiring"]
    assert result["problem_context"]["problem_id"] == "prob-1"


@patch("api_server.generate_jugaad_fix_guidance")
def test_jugaad_help_endpoint_forwards_uploads(mock_generate):
    mock_generate.return_value = {
        "source": "gemini",
        "confidence": 0.82,
        "situation_summary": "A temporary brace is possible.",
        "materials_identified": ["tube", "wire"],
        "temporary_fix_steps": ["Step 1"],
        "safety_warnings": ["Warning 1"],
        "when_to_stop": "Stop if pressure rises.",
        "escalation": "Escalate to the mechanic.",
    }

    response = asyncio.run(
        api_server.jugaad_help(
            broken_photo=UploadFile(filename="broken.jpg", file=io.BytesIO(b"broken-bytes")),
            materials_photo=UploadFile(filename="materials.jpg", file=io.BytesIO(b"materials-bytes")),
            problem_title="Broken pump",
            problem_description="Pump coupling is leaking",
            category="infrastructure",
            village_name="Sundarpur",
            problem_id="prob-99",
        )
    )

    assert response["status"] == "success"
    assert response["guidance"]["source"] == "gemini"
    mock_generate.assert_called_once()
    args, kwargs = mock_generate.call_args
    assert len(args) == 2
    assert kwargs["problem_title"] == "Broken pump"
    assert kwargs["problem_id"] == "prob-99"


if __name__ == "__main__":
    pytest.main([__file__])
