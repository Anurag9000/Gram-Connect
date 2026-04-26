import json
import logging
import mimetypes
import os
import re
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional

from env_loader import load_local_env
from path_utils import ensure_runtime_dir

load_local_env()

logger = logging.getLogger("multimodal_service")

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_AUDIO_MODEL = os.getenv("GEMINI_AUDIO_MODEL", "gemini-2.5-flash")
DEFAULT_IMAGE_MODEL = os.getenv("GEMINI_VISION_MODEL", DEFAULT_GEMINI_MODEL)
DEFAULT_PROOF_MODEL = os.getenv("GEMINI_PROOF_MODEL", DEFAULT_IMAGE_MODEL)

_gemini_client = None
_whisper_model = None
_clip_model = None
_clip_preprocess = None
_torch_module = None


def _load_module(name: str):
    return import_module(name)


def _load_torch():
    global _torch_module
    if _torch_module is None:
        _torch_module = _load_module("torch")
    return _torch_module


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
                shim_path.write_bytes(ffmpeg_path.read_bytes())
            shim_path.chmod(0o755)
        current_path = os.environ.get("PATH", "")
        path_parts = current_path.split(os.pathsep) if current_path else []
        shim_dir_str = str(shim_dir)
        if shim_dir_str not in path_parts:
            os.environ["PATH"] = os.pathsep.join([shim_dir_str, current_path]) if current_path else shim_dir_str
    except Exception as exc:
        logger.warning("Failed to provision bundled ffmpeg binary: %s", exc)


def _has_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
          _gemini_client = genai.Client(api_key=api_key)
        else:
          _gemini_client = genai.Client()
    return _gemini_client


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Empty Gemini response")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _normalize_tags(raw_tags: Any, top_label: str) -> List[str]:
    if isinstance(raw_tags, list):
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    elif isinstance(raw_tags, str):
        tags = [part.strip() for part in raw_tags.split(",") if part.strip()]
    else:
        tags = []

    if top_label and top_label not in tags:
        tags.insert(0, top_label)
    # Keep the frontend payload small and stable.
    return tags[:5]


@lru_cache(maxsize=1)
def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _ensure_ffmpeg_on_path()
        whisper = _load_module("whisper")
        logger.info("Loading Whisper 'tiny' model for fallback transcription...")
        _whisper_model = whisper.load_model("tiny")
    return _whisper_model


@lru_cache(maxsize=1)
def get_clip():
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        try:
            clip = _load_module("clip")
            torch = _load_torch()
            logger.info("Loading CLIP 'ViT-B/32' fallback model...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _clip_model, _clip_preprocess = clip.load("ViT-B/32", device=device)
        except ImportError:
            logger.warning("CLIP fallback not installed.")
            return None, None
    return _clip_model, _clip_preprocess


def _extract_transcript_payload(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        return {"text": "", "language": None, "source": None}

    try:
        payload = _extract_json_object(cleaned)
        transcript = str(
            payload.get("text")
            or payload.get("transcript")
            or payload.get("transcript_text")
            or ""
        ).strip()
        language_code = str(
            payload.get("language_code")
            or payload.get("language")
            or payload.get("detected_language")
            or ""
        ).strip()
        language_name = str(payload.get("language_name") or payload.get("language_label") or "").strip()
        source = str(payload.get("source") or "").strip()
    except Exception:
        transcript = cleaned
        language_code = ""
        language_name = ""
        source = ""

    resolved_language = language_code or language_name
    return {
        "text": transcript,
        "language": resolved_language or None,
        "language_code": language_code or None,
        "language_name": language_name or None,
        "source": source or None,
    }


def transcribe_audio(audio_path: str) -> Dict[str, Any]:
    """Transcribe audio with Gemini first, then Whisper as a fallback.

    The returned transcript preserves the original spoken language and script.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if _has_gemini_key():
        try:
            client = get_gemini_client()
            mime_type = mimetypes.guess_type(audio_path)[0] or "audio/wav"
            audio_bytes = _read_file_bytes(audio_path)
            from google.genai import types

            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            response = client.models.generate_content(
                model=DEFAULT_AUDIO_MODEL,
                contents=[
                    (
                        "Transcribe the audio exactly as spoken.\n"
                        "Preserve the original language and writing script.\n"
                        "Do not translate, transliterate, summarize, or normalize the text.\n"
                        "If the speaker code-switches, keep the mixed-language transcript as spoken.\n"
                        "Return strict JSON with keys:\n"
                        '  "text": the verbatim transcript in the original language/script,\n'
                        '  "language_code": the primary spoken language ISO code if identifiable,\n'
                        '  "language_name": the primary spoken language name if identifiable,\n'
                        '  "source": "gemini".\n'
                        "Do not include markdown, explanations, or extra keys."
                    ),
                    audio_part,
                ],
            )
            payload = _extract_transcript_payload(response.text or "{}")
            if payload["text"]:
                return payload
            logger.warning("Gemini transcription returned empty text; falling back to Whisper.")
        except Exception as exc:
            logger.warning("Gemini transcription failed, falling back to Whisper: %s", exc)

    model = get_whisper()
    result = model.transcribe(audio_path)
    transcript = str(result.get("text", "")).strip()
    language_code = result.get("language")
    return {
        "text": transcript,
        "language": language_code,
        "language_code": language_code,
        "language_name": result.get("language_name"),
        "source": "whisper",
    }


def analyze_image(image_path: str, candidate_labels: list = None) -> dict:
    """Classify an image with Gemini first, then CLIP as a fallback."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    labels = [str(label).strip() for label in (candidate_labels or []) if str(label).strip()]
    if not labels:
        labels = [
            "infrastructure damage",
            "water pollution",
            "medical emergency",
            "digital literacy",
            "education",
            "agriculture",
            "livestock",
            "sanitation issue",
            "broken pump",
            "road repair",
        ]

    if _has_gemini_key():
        try:
            client = get_gemini_client()
            image_bytes = _read_file_bytes(image_path)
            mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            from google.genai import types

            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            prompt = (
                "You are classifying rural community problem photos for Gram Connect.\n"
                f"Choose the best label from this candidate set: {', '.join(labels)}.\n"
                "Return only valid JSON with keys:\n"
                '  "top_label": the best matching label,\n'
                '  "confidence": a number from 0 to 1,\n'
                '  "tags": an array of up to 5 short labels, ordered by relevance,\n'
                '  "all_probs": an object mapping each candidate label to a number from 0 to 1.\n'
                "Do not include markdown, explanations, or extra keys."
            )
            response = client.models.generate_content(
                model=DEFAULT_IMAGE_MODEL,
                contents=[image_part, prompt],
            )
            parsed = _extract_json_object(response.text or "{}")
            top_label = str(parsed.get("top_label") or labels[0]).strip()
            tags = _normalize_tags(parsed.get("tags"), top_label)
            all_probs = parsed.get("all_probs")
            if not isinstance(all_probs, dict):
                all_probs = {label: float(parsed.get("confidence", 0.0)) if label == top_label else 0.0 for label in labels}

            confidence = parsed.get("confidence", 0.0)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.0

            return {
                "top_label": top_label,
                "confidence": confidence,
                "all_probs": all_probs,
                "tags": tags,
            }
        except Exception as exc:
            logger.warning("Gemini image analysis failed, falling back to CLIP: %s", exc)

    model, preprocess = get_clip()
    if model is None:
        return {
            "top_label": "N/A (CLIP Missing)",
            "confidence": 0.0,
            "all_probs": {},
            "tags": [],
        }

    clip = _load_module("clip")
    torch = _load_torch()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        from PIL import Image

        with Image.open(image_path) as img:
            image_input = preprocess(img).unsqueeze(0).to(device)
    except Exception as exc:
        logger.error("Failed to open/preprocess image: %s", exc)
        return {
            "top_label": "Error",
            "confidence": 0.0,
            "all_probs": {"error": str(exc)},
            "tags": [],
        }

    text_input = clip.tokenize(labels).to(device)

    with torch.no_grad():
        logits_per_image, _ = model(image_input, text_input)
        probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

    results = {label: float(prob) for label, prob in zip(labels, probs)}
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


def infer_problem_severity(title: str, description: str, tags: List[str]) -> str:
    """Use Gemini to intelligently infer problem severity (LOW, NORMAL, HIGH) from multimodal context."""
    if not _has_gemini_key():
        # Fallback to simple keyword logic if offline
        from nexus import estimate_severity, SEVERITY_LABELS
        full_text = f"{title} {description} {' '.join(tags)}".lower()
        return SEVERITY_LABELS.get(estimate_severity(full_text), "NORMAL")

    try:
        client = get_gemini_client()
        tags_str = ", ".join(tags) if tags else "None"
        prompt = (
            "You are an AI triaging problems reported by villagers in rural India.\n"
            "Given the problem title, description, and visual tags extracted from photos, classify the severity as LOW, NORMAL, or HIGH.\n\n"
            "- HIGH: Medical emergencies, immediate safety hazards (e.g., live wires, fires, building collapse, flooding, violent conflict).\n"
            "- NORMAL: Standard infrastructure issues (e.g., broken handpump, potholes, power outage, agricultural pests).\n"
            "- LOW: Minor routine requests (e.g., asking for information, small cosmetic repairs, general cleaning).\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Visual Tags: {tags_str}\n\n"
            "Return strict JSON only with keys:\n"
            '  "severity": exactly one of "LOW", "NORMAL", or "HIGH"\n'
            '  "reason": one short sentence explaining why.\n'
        )
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=[prompt],
        )
        parsed = _extract_json_object(response.text or "{}")
        severity = str(parsed.get("severity") or "NORMAL").upper()
        if severity not in ["LOW", "NORMAL", "HIGH"]:
            severity = "NORMAL"
        return severity
    except Exception as exc:
        logger.warning("Gemini severity inference failed: %s", exc)
        return "NORMAL"



def verify_resolution_proof(
    before_image_path: Optional[str],
    after_image_path: str,
    *,
    problem_title: str,
    problem_description: str,
    category: Optional[str] = None,
    visual_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Validate before/after proof with Gemini.

    Accept only when the after image plausibly shows the reported issue resolved or improved.
    """
    if not after_image_path or not os.path.exists(after_image_path):
        raise FileNotFoundError("After image file is required for proof verification.")

    if not _has_gemini_key():
        return {
            "accepted": False,
            "confidence": 0.0,
            "summary": "Proof verification unavailable because Gemini is not configured.",
            "detected_change": "unknown",
            "source": "none",
        }

    client = get_gemini_client()
    from google.genai import types

    parts: List[Any] = []
    if before_image_path and os.path.exists(before_image_path):
        before_mime = mimetypes.guess_type(before_image_path)[0] or "image/jpeg"
        parts.append(types.Part.from_bytes(data=_read_file_bytes(before_image_path), mime_type=before_mime))
    after_mime = mimetypes.guess_type(after_image_path)[0] or "image/jpeg"
    parts.append(types.Part.from_bytes(data=_read_file_bytes(after_image_path), mime_type=after_mime))

    tags_text = ", ".join(visual_tags or [])
    prompt = (
        "You are validating field-work completion proof for Gram Connect.\n"
        "The first image is BEFORE if present. The last image is AFTER.\n"
        "Determine whether the AFTER image plausibly shows the reported issue fixed or materially improved.\n"
        "You must also determine whether the uploaded images actually match the described task domain.\n"
        "Reject unrelated image pairs, category-mismatched uploads, cosmetic-only changes, or unverifiable outcomes.\n"
        f"Problem title: {problem_title}\n"
        f"Problem description: {problem_description}\n"
        f"Problem category: {category or 'unknown'}\n"
        f"Problem visual tags: {tags_text or 'none'}\n"
        "Return strict JSON only with keys:\n"
        '  "accepted": boolean,\n'
        '  "confidence": number from 0 to 1,\n'
        '  "task_match": boolean,\n'
        '  "same_scene": boolean,\n'
        '  "issue_fixed": boolean,\n'
        '  "summary": short one-sentence reason,\n'
        '  "detected_change": short phrase describing the visible change,\n'
        '  "source": "gemini".\n'
        "Examples of rejection:\n"
        "- uploading pothole images for a digital literacy task\n"
        "- uploading two unrelated photos from different contexts\n"
        "- uploading random scenery with no visible task outcome\n"
        "Accept only if all of these are true: the images match the task domain, the before/after are plausibly about the same task or scene, and the after image clearly shows resolution or material improvement."
    )

    model_candidates: List[str] = []
    for candidate in [DEFAULT_PROOF_MODEL, DEFAULT_IMAGE_MODEL, DEFAULT_GEMINI_MODEL, "gemini-2.5-flash"]:
        candidate = str(candidate).strip()
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)

    last_error: Optional[Exception] = None
    parsed: Optional[Dict[str, Any]] = None
    chosen_model = model_candidates[0]
    for model_name in model_candidates:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[*parts, prompt],
            )
            parsed = _extract_json_object(response.text or "{}")
            chosen_model = model_name
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Proof verification failed with Gemini model %s: %s", model_name, exc)
            continue

    if parsed is None:
        raise RuntimeError(f"Gemini proof verification failed across models: {last_error}")

    task_match = bool(parsed.get("task_match"))
    same_scene = bool(parsed.get("same_scene"))
    issue_fixed = bool(parsed.get("issue_fixed"))
    accepted = bool(parsed.get("accepted")) and task_match and same_scene and issue_fixed
    confidence = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "accepted": accepted,
        "confidence": confidence,
        "task_match": task_match,
        "same_scene": same_scene,
        "issue_fixed": issue_fixed,
        "summary": str(parsed.get("summary") or "").strip() or "No summary returned.",
        "detected_change": str(parsed.get("detected_change") or "").strip() or "unknown",
        "source": str(parsed.get("source") or f"gemini:{chosen_model}"),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Multimodal Service: Gemini-first with local fallbacks for offline development.")

def extract_problem_from_whatsapp(transcript: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Use Gemini to extract structured problem details from a raw WhatsApp message (audio transcript + optional image)."""
    if not _has_gemini_key():
        return {
            "title": "Raw WhatsApp Report",
            "description": transcript or "No audio provided.",
            "village_name": "Unknown",
            "category": "infrastructure",
            "severity": "NORMAL"
        }

    try:
        client = get_gemini_client()
        from google.genai import types
        
        parts: List[Any] = []
        if image_path and os.path.exists(image_path):
            mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            parts.append(types.Part.from_bytes(data=_read_file_bytes(image_path), mime_type=mime_type))
            
        prompt = (
            "You are a rural coordinator AI for Gram Connect.\n"
            "A villager has sent a WhatsApp message (a transcribed voice note and optionally a photo).\n"
            "Extract the structured details from this message.\n\n"
            f"Transcript: \"{transcript}\"\n\n"
            "Categories allowed: water-sanitation, infrastructure, health-medical, agriculture, digital-literacy, environment, community.\n"
            "Return strict JSON with keys:\n"
            '  "title": a short 3-5 word summary,\n'
            '  "description": a clean, readable version of their problem,\n'
            '  "village_name": the village name if mentioned, otherwise "Unknown",\n'
            '  "category": the best matching category from the allowed list,\n'
            '  "severity": "LOW", "NORMAL", or "HIGH".\n'
        )
        parts.append(prompt)
        
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=parts,
        )
        
        parsed = _extract_json_object(response.text or "{}")
        return {
            "title": str(parsed.get("title") or "WhatsApp Report").strip(),
            "description": str(parsed.get("description") or transcript).strip(),
            "village_name": str(parsed.get("village_name") or "Unknown").strip(),
            "category": str(parsed.get("category") or "infrastructure").strip().lower(),
            "severity": str(parsed.get("severity") or "NORMAL").upper()
        }
    except Exception as exc:
        logger.warning("Gemini WhatsApp extraction failed: %s", exc)
        return {
            "title": "Raw WhatsApp Report",
            "description": transcript or "Extraction failed.",
            "village_name": "Unknown",
            "category": "infrastructure",
            "severity": "NORMAL"
        }
