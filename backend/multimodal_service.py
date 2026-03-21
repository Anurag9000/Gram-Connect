import os
import shutil
from PIL import Image
import logging
from importlib import import_module
from pathlib import Path

from path_utils import ensure_runtime_dir

logger = logging.getLogger("multimodal_service")

# Global models (Lazy loading)
_whisper_model = None
_clip_model = None
_clip_preprocess = None
_torch_module = None


def _load_torch():
    global _torch_module
    if _torch_module is None:
        _torch_module = import_module("torch")
    return _torch_module


def _load_module(name: str):
    return import_module(name)


def _ensure_ffmpeg_on_path():
    try:
        ffmpeg_module = _load_module("imageio_ffmpeg")
        ffmpeg_path = Path(ffmpeg_module.get_ffmpeg_exe())
        shim_dir = Path(ensure_runtime_dir()) / "bin"
        shim_dir.mkdir(parents=True, exist_ok=True)
        shim_path = shim_dir / "ffmpeg"
        if not shim_path.exists():
            try:
                shim_path.symlink_to(ffmpeg_path)
            except OSError:
                shutil.copy2(ffmpeg_path, shim_path)
            shim_path.chmod(0o755)
        current_path = os.environ.get("PATH", "")
        path_parts = current_path.split(os.pathsep) if current_path else []
        shim_dir_str = str(shim_dir)
        if shim_dir_str not in path_parts:
            os.environ["PATH"] = os.pathsep.join([shim_dir_str, current_path]) if current_path else shim_dir_str
    except Exception as exc:
        logger.warning("Failed to provision bundled ffmpeg binary: %s", exc)

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _ensure_ffmpeg_on_path()
        whisper = _load_module("whisper")
        logger.info("Loading Whisper 'tiny' model...")
        _whisper_model = whisper.load_model("tiny")
    return _whisper_model

def get_clip():
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        try:
            clip = _load_module("clip")
            torch = _load_torch()
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
            "all_probs": {},
            "tags": []
        }
    
    clip = _load_module("clip")
    torch = _load_torch()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    try:
        with Image.open(image_path) as img:
            image_input = preprocess(img).unsqueeze(0).to(device)
    except Exception as e:
        logger.error(f"Failed to open/preprocess image: {e}")
        return {
            "top_label": "Error",
            "confidence": 0.0,
            "all_probs": {"error": str(e)},
            "tags": []
        }
    
    text_input = clip.tokenize(candidate_labels).to(device)

    with torch.no_grad():
        logits_per_image, logits_per_text = model(image_input, text_input)
        probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

    # Map labels to probabilities
    results = {label: float(prob) for label, prob in zip(candidate_labels, probs)}
    
    # Get top prediction
    top_label = max(results, key=results.get)
    sorted_labels = sorted(results.items(), key=lambda item: item[1], reverse=True)
    tags = [label for label, score in sorted_labels if score >= 0.15][:3]
    if not tags and top_label:
        tags = [top_label]
    
    return {
        "top_label": top_label,
        "confidence": results[top_label],
        "all_probs": results,
        "tags": tags,
    }

if __name__ == "__main__":
    # Internal test check
    logging.basicConfig(level=logging.INFO)
    print("Multimodal Service: Static check complete. Lazy loading models on call.")
