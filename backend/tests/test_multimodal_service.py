import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import multimodal_service

@patch('whisper.load_model')
def test_get_whisper(mock_load):
    multimodal_service._whisper_model = None
    multimodal_service.get_whisper()
    mock_load.assert_called_with("tiny")

@patch('multimodal_service.get_whisper')
@patch('os.path.exists')
def test_transcribe_audio(mock_exists, mock_get_w):
    mock_exists.return_value = True
    model = mock_get_w.return_value
    model.transcribe.return_value = {"text": " hello world "}
    
    res = multimodal_service.transcribe_audio("fake_path.mp3")
    assert res == "hello world"

@patch('multimodal_service.get_clip')
@patch('os.path.exists')
@patch('PIL.Image.open')
def test_analyze_image_success(mock_img_open, mock_exists, mock_get_clip):
    mock_exists.return_value = True
    model = MagicMock()
    preprocess = MagicMock()
    mock_get_clip.return_value = (model, preprocess)
    
    # Mocking model call results
    import torch
    mock_logits = torch.tensor([[10.0, 1.0]]) # Very high logit for first label
    model.return_value = (mock_logits, None)
    
    # Create a mock for the clip module
    mock_clip = MagicMock()
    mock_clip.tokenize.return_value = torch.zeros((2, 77))
    
    # Patch sys.modules to include our mock clip
    with patch.dict('sys.modules', {'clip': mock_clip}):
        res = multimodal_service.analyze_image("fake.jpg", ["label1", "label2"])
        assert res["top_label"] == "label1"
        assert res["confidence"] > 0.9

@patch('multimodal_service.get_clip')
@patch('os.path.exists')
def test_analyze_image_no_clip(mock_exists, mock_get_clip):
    mock_exists.return_value = True
    mock_get_clip.return_value = (None, None)
    
    res = multimodal_service.analyze_image("fake.jpg")
    assert res["top_label"] == "N/A (CLIP Missing)"

if __name__ == "__main__":
    pytest.main([__file__])
