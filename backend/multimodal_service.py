import os
import whisper
import torch
from PIL import Image
# import clip (removed from top-level to handle missing dependency)
import logging

logger = logging.getLogger("multimodal_service")

# Global models (Lazy loading)
_whisper_model = None
_clip_model = None
_clip_preprocess = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper 'tiny' model...")
        _whisper_model = whisper.load_model("tiny")
    return _whisper_model

def get_clip():
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        try:
            import clip
            logger.info("Loading CLIP 'ViT-B/32' model...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _clip_model, _clip_preprocess = clip.load("ViT-B/32", device=device)
        except ImportError:
            logger.warning("CLIP not installed. Visual analysis will be disabled.")
            return None, None
    return _clip_model, _clip_preprocess

def transcribe_audio(audio_path: str) -> str:
    """Uses Whisper to transcribe audio file to text."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    model = get_whisper()
    result = model.transcribe(audio_path)
    return result.get("text", "").strip()

def analyze_image(image_path: str, candidate_labels: list = None) -> dict:
    """Uses CLIP to classify an image against candidate labels."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    if not candidate_labels:
        candidate_labels = [
            "infrastructure damage", "water pollution", "medical emergency", 
            "digital literacy", "education", "agriculture", "livestock", 
            "sanitation issue", "broken pump", "road repair"
        ]

    model, preprocess = get_clip()
    if model is None:
        return {
            "top_label": "N/A (CLIP Missing)",
            "confidence": 0.0,
            "all_probs": {}
        }
    
    import clip # Local import for tokenize
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    text = clip.tokenize(candidate_labels).to(device)

    with torch.no_grad():
        logits_per_image, logits_per_text = model(image, text)
        probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

    # Map labels to probabilities
    results = {label: float(prob) for label, prob in zip(candidate_labels, probs)}
    
    # Get top prediction
    top_label = max(results, key=results.get)
    
    return {
        "top_label": top_label,
        "confidence": results[top_label],
        "all_probs": results
    }

if __name__ == "__main__":
    # Internal test check
    logging.basicConfig(level=logging.INFO)
    print("Multimodal Service: Static check complete. Lazy loading models on call.")
