import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multimodal_service


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
@patch("multimodal_service.analyze_image")
@patch("multimodal_service.get_gemini_client")
def test_suggest_jugaad_fix_uses_gemini(mock_get_client, mock_analyze_image, mock_exists, mock_read_bytes, mock_has_key):
    response = MagicMock()
    response.text = """
    {
      "summary": "Use the tube as a temporary seal around the leak.",
      "problem_read": "A cracked handpump joint with spare wire and tube available.",
      "observed_broken_part": "handpump joint",
      "observed_materials": "rubber tube and wire",
      "temporary_fix": "Wrap the joint externally and secure it gently.",
      "step_by_step": ["Shut off water", "Dry the joint", "Wrap with tube", "Secure with wire"],
      "safety_notes": ["Keep pressure low", "Do not open live electrical parts"],
      "materials_to_use": ["rubber tube", "wire"],
      "materials_to_avoid": ["sharp metal", "open flames"],
      "when_to_stop": ["If the leak worsens"],
      "needs_official_part": true,
      "confidence": 0.84,
      "source": "gemini"
    }
    """
    client = MagicMock()
    client.models.generate_content.return_value = response
    mock_get_client.return_value = client
    mock_analyze_image.side_effect = [
        {"top_label": "handpump", "confidence": 0.9, "tags": ["handpump"]},
        {"top_label": "rubber tube", "confidence": 0.9, "tags": ["rubber tube", "wire"]},
    ]

    result = multimodal_service.suggest_jugaad_fix(
        "broken.jpg",
        "materials.jpg",
        problem_title="Broken handpump",
        problem_description="Water is leaking at the joint",
        category="infrastructure",
        visual_tags=["handpump"],
        materials_note="rubber tube and wire",
    )

    assert result["summary"].startswith("Use the tube")
    assert result["needs_official_part"] is True
    assert result["step_by_step"][0] == "Shut off water"
    assert client.models.generate_content.called


@patch("multimodal_service._has_gemini_key", return_value=False)
def test_suggest_immediate_problem_actions_uses_fallback(mock_has_key):
    result = multimodal_service.suggest_immediate_problem_actions(
        problem_title="Broken handpump",
        problem_description="Water is leaking from the joint",
        category="water-sanitation",
        visual_tags=["handpump", "water"],
        severity="NORMAL",
    )

    assert result["topic"] == "water"
    assert result["what_you_can_do_now"]
    assert any("pressure" in step.lower() or "seal" in step.lower() for step in result["what_you_can_do_now"])
    assert result["materials_to_find"]


if __name__ == "__main__":
    pytest.main([__file__])
