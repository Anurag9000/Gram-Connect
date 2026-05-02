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

_TOPIC_KEYWORDS = {
    "water": [
        "water",
        "pump",
        "handpump",
        "pipeline",
        "pipe",
        "tap",
        "leak",
        "well",
        "bore",
        "tank",
        "sanitation",
    ],
    "health": [
        "health",
        "fever",
        "sickness",
        "dengue",
        "malaria",
        "clinic",
        "medicine",
        "outbreak",
        "cough",
        "infection",
    ],
    "infrastructure": [
        "road",
        "bridge",
        "building",
        "pole",
        "wire",
        "power",
        "inverter",
        "roof",
        "wall",
        "structure",
    ],
    "agriculture": [
        "crop",
        "field",
        "irrigation",
        "farming",
        "farm",
        "seed",
        "harvest",
        "soil",
        "livestock",
        "pump",
    ],
    "digital": [
        "computer",
        "internet",
        "mobile",
        "phone",
        "app",
        "software",
        "printer",
        "tablet",
        "network",
        "digital",
    ],
}


def _load_module(name: str):
    return import_module(name)


def _load_torch():
    global _torch_module
    if _torch_module is None:
        _torch_module = _load_module("torch")
    return _torch_module


def _resolve_device(torch_module) -> str:
    """Prefer CPU unless the caller explicitly opts into CUDA."""
    use_cuda = os.getenv("GRAM_CONNECT_USE_CUDA", "").strip().lower() in {"1", "true", "yes", "on"}
    if not use_cuda:
        return "cpu"
    try:
        if torch_module.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


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


def _get_gemini_types():
    try:
        from google.genai import types  # type: ignore

        return types
    except Exception as exc:
        logger.debug("Gemini types unavailable: %s", exc)
        return None


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
            device = _resolve_device(torch)
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
            types = _get_gemini_types()
            if types is None:
                raise RuntimeError("Gemini types unavailable")

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

    try:
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
    except Exception as exc:
        logger.warning("Whisper fallback unavailable, returning empty transcript: %s", exc)
        return {
            "text": "",
            "language": None,
            "language_code": None,
            "language_name": None,
            "source": "unavailable",
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
            types = _get_gemini_types()
            if types is None:
                raise RuntimeError("Gemini types unavailable")

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
    device = _resolve_device(torch)

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
    types = _get_gemini_types()
    if types is None:
        return {
            "accepted": False,
            "confidence": 0.0,
            "task_match": False,
            "same_scene": False,
            "issue_fixed": False,
            "summary": "Proof verification unavailable because Gemini types are not configured.",
            "detected_change": "unknown",
            "source": "none",
        }

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


def _normalize_jugaad_list(value: Any) -> List[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        items = [part.strip() for part in re.split(r"[\n,;]+", value) if part.strip()]
    else:
        items = []

    deduped: List[str] = []
    seen = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:8]


def _jugaad_fallback_plan(
    *,
    problem_title: str,
    problem_description: str,
    category: Optional[str],
    broken_analysis: Dict[str, Any],
    materials_analysis: Dict[str, Any],
    materials_note: Optional[str],
) -> Dict[str, Any]:
    broken_label = str(broken_analysis.get("top_label") or "").lower()
    broken_tags = " ".join(str(tag).lower() for tag in (broken_analysis.get("tags") or []))
    materials_text = " ".join(str(tag).lower() for tag in (materials_analysis.get("tags") or []))
    materials_text = f"{materials_text} {str(materials_note or '').lower()}".strip()

    is_electrical = any(token in f"{broken_label} {broken_tags}" for token in ["electrical", "inverter", "wire", "solar", "battery", "switch", "cable"])
    is_water_system = any(token in f"{broken_label} {broken_tags}" for token in ["pump", "handpump", "pipe", "valve", "leak", "borewell", "tap", "hose"])
    has_clamp_materials = any(token in materials_text for token in ["wire", "tube", "bamboo", "rope", "cloth", "tape", "rubber", "strip"])

    if is_electrical:
        summary = "The photos suggest an electrical or solar component issue, so the safest move is to avoid opening live equipment and only do external stabilization."
        temporary_fix = "Isolate the area, keep everything dry, and use the available materials only to support loose cables or protect a damaged outer casing."
        steps = [
            "Switch off power at the safest isolation point before touching the unit.",
            "Check only the outside of the housing for loose cables, cracked covers, or obvious breaks.",
            "Use dry bamboo, wood, or tape to support dangling wires or a loose cover without exposing live parts.",
            "Keep water away from the unit and do a short test only after the area is dry and stable.",
        ]
        safety_notes = [
            "Do not open the inverter, battery, or controller if there is any chance of live power.",
            "Do not use wet cloth, metal wire, or bare hands near exposed terminals.",
        ]
        materials_to_use = ["dry bamboo", "wood support", "tape", "cloth for drying"]
        materials_to_avoid = ["exposed metal", "wet cloth", "bare wire contact", "anything that bypasses a fuse"]
        when_to_stop = [
            "You smell burning or see sparking.",
            "The casing is hot, cracked, or exposed wires are live.",
            "The unit trips again immediately after reset.",
        ]
        needs_official_part = True
    elif is_water_system:
        if has_clamp_materials:
            summary = "The photos look like a water-flow or pump problem, and you may be able to keep water moving with a temporary external seal or brace."
            temporary_fix = "Build a temporary external clamp or wrap around the leak or loose joint, then test the flow slowly at low pressure."
            steps = [
                "Shut off the water or reduce pressure before making any repair.",
                "Dry the leak point and inspect whether the issue is a loose joint, cracked hose, or slipping seal.",
                "Wrap the damaged section with rubber tube, cloth, or tape and secure it tightly with wire or bamboo bracing from the outside.",
                "Test with a small amount of flow first, and tighten again if the leak returns.",
            ]
            safety_notes = [
                "This is only a temporary fix to keep service running until the proper part arrives.",
                "Stop if the repair point bulges, sprays, or the structure starts to flex.",
            ]
            materials_to_use = ["rubber tube", "wire", "bamboo brace", "cloth wrap", "tape"]
            materials_to_avoid = ["metal pieces that cut into the hose", "anything that blocks the water path", "glue on a pressurized joint"]
            when_to_stop = [
                "Water pressure is too high to hold with a wrap.",
                "The pipe or pump housing is cracked open.",
                "There is electrical equipment nearby that is wet or unstable.",
            ]
            needs_official_part = True
        else:
            summary = "The photos suggest a water-system problem, but the available materials do not look strong enough for a safe temporary clamp."
            temporary_fix = "Use only a very light external support, keep the area dry, and avoid forcing the part back into place."
            steps = [
                "Reduce pressure and inspect the exact broken point.",
                "Use only external support to keep the part aligned; do not force a cracked piece together.",
                "Keep the pump or pipe under minimal load until a proper clamp or spare part is available.",
            ]
            safety_notes = [
                "Do not seal a major crack with weak materials if it could burst under pressure.",
                "Escalate quickly if the part is carrying load or water pressure cannot be reduced.",
            ]
            materials_to_use = ["bamboo support", "cloth padding", "light tape for alignment"]
            materials_to_avoid = ["thin wire on a pressurized crack", "heavy impact", "glue as a structural repair"]
            when_to_stop = [
                "The leak is growing instead of shrinking.",
                "The pipe moves under pressure.",
                "You cannot safely lower the flow before repair.",
            ]
            needs_official_part = True
    else:
        summary = "The photos show a general mechanical issue, so only use the materials for external bracing and temporary protection."
        temporary_fix = "Keep the mechanism stable, protect the damaged area from further stress, and use only non-invasive external reinforcement."
        steps = [
            "Identify the loose or broken external point without dismantling the unit.",
            "Use bamboo, cloth, rope, or wire to steady the part externally.",
            "Test the mechanism slowly and stop if the movement becomes unsafe or noisy.",
        ]
        safety_notes = [
            "Avoid opening sealed housing or modifying internal parts.",
            "If the repair needs alignment under load, escalate to a technician.",
        ]
        materials_to_use = ["bamboo", "cloth", "rope", "wire", "tape"]
        materials_to_avoid = ["heavy force", "internal tampering", "sharp metal that can cut cables or hoses"]
        when_to_stop = [
            "The part is structural, load-bearing, or electrical.",
            "The fix requires removing sealed covers.",
            "The temporary support slips or cracks under load.",
        ]
        needs_official_part = True

    confidence = float(min(0.92, 0.48 + 0.06 * len(_normalize_jugaad_list(materials_analysis.get("tags") or [])) + (0.1 if has_clamp_materials else 0.0)))
    if is_electrical:
        confidence = min(confidence, 0.72)

    return {
        "summary": summary,
        "problem_read": f"{problem_title}: {problem_description}".strip(": "),
        "observed_broken_part": str(broken_analysis.get("top_label") or "unclear"),
        "observed_materials": ", ".join(_normalize_jugaad_list(materials_analysis.get("tags") or [])) or str(materials_analysis.get("top_label") or "unclear"),
        "temporary_fix": temporary_fix,
        "step_by_step": steps,
        "safety_notes": safety_notes,
        "materials_to_use": materials_to_use,
        "materials_to_avoid": materials_to_avoid,
        "when_to_stop": when_to_stop,
        "needs_official_part": needs_official_part,
        "confidence": round(confidence, 3),
        "source": "heuristic",
    }


def suggest_jugaad_fix(
    broken_image_path: str,
    materials_image_path: str,
    *,
    problem_title: str,
    problem_description: str,
    category: Optional[str] = None,
    visual_tags: Optional[List[str]] = None,
    materials_note: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a safe temporary repair plan from a broken-part photo and a materials photo."""
    if not broken_image_path or not os.path.exists(broken_image_path):
        raise FileNotFoundError("Broken-part image is required for Jugaad guidance.")
    if not materials_image_path or not os.path.exists(materials_image_path):
        raise FileNotFoundError("Available-materials image is required for Jugaad guidance.")

    broken_analysis = analyze_image(
        broken_image_path,
        ["handpump", "pipe leak", "valve", "solar inverter", "electrical box", "motor", "broken bracket", "loose cable", "general mechanism"],
    )
    materials_analysis = analyze_image(
        materials_image_path,
        ["rubber tube", "wire", "bamboo", "rope", "cloth", "wood plank", "metal strip", "tape", "tools", "misc materials"],
    )

    if not _has_gemini_key():
        return _jugaad_fallback_plan(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            broken_analysis=broken_analysis,
            materials_analysis=materials_analysis,
            materials_note=materials_note,
        )

    client = get_gemini_client()
    types = _get_gemini_types()
    if types is None:
        return _jugaad_fallback_plan(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            broken_analysis=broken_analysis,
            materials_analysis=materials_analysis,
            materials_note=materials_note,
        )

    broken_mime = mimetypes.guess_type(broken_image_path)[0] or "image/jpeg"
    materials_mime = mimetypes.guess_type(materials_image_path)[0] or "image/jpeg"
    parts: List[Any] = [
        types.Part.from_bytes(data=_read_file_bytes(broken_image_path), mime_type=broken_mime),
        types.Part.from_bytes(data=_read_file_bytes(materials_image_path), mime_type=materials_mime),
    ]

    prompt = (
        "You are Gram Connect's Jugaad Engine, a cautious frugal-innovation assistant for field volunteers.\n"
        "Analyze the broken mechanism photo and the available-materials photo together.\n"
        "Your job is to suggest a safe, temporary, external repair that keeps the service running until the official part arrives.\n"
        "Do not suggest dangerous internal electrical work, bypassing safety devices, or permanent hacks.\n"
        "If the task looks unsafe, refuse the risky repair and recommend escalation.\n\n"
        f"Problem title: {problem_title}\n"
        f"Problem description: {problem_description}\n"
        f"Problem category: {category or 'unknown'}\n"
        f"Visual tags: {', '.join(visual_tags or []) or 'none'}\n"
        f"Extra materials note: {materials_note or 'none'}\n"
        f"Gemini observations placeholder broken: {json.dumps(broken_analysis, default=str)[:900]}\n"
        f"Gemini observations placeholder materials: {json.dumps(materials_analysis, default=str)[:900]}\n\n"
        "Return strict JSON only with these keys:\n"
        '  "summary": one concise sentence describing the temporary repair idea,\n'
        '  "problem_read": short description of what the broken part appears to be,\n'
        '  "observed_broken_part": short phrase naming the broken component,\n'
        '  "observed_materials": short phrase naming the useful materials visible,\n'
        '  "temporary_fix": one sentence explaining the makeshift repair,\n'
        '  "step_by_step": array of 3 to 6 short, numbered-style steps,\n'
        '  "safety_notes": array of safety warnings,\n'
        '  "materials_to_use": array of useful materials from the photo,\n'
        '  "materials_to_avoid": array of risky or unsuitable materials,\n'
        '  "when_to_stop": array of conditions that mean the volunteer must stop,\n'
        '  "needs_official_part": boolean,\n'
        '  "confidence": number from 0 to 1,\n'
        '  "source": "gemini".\n'
        "Keep the advice temporary, external, and field-practical."
    )

    model_candidates: List[str] = []
    for candidate in [DEFAULT_IMAGE_MODEL, DEFAULT_GEMINI_MODEL, "gemini-2.5-flash"]:
        candidate = str(candidate).strip()
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)

    parsed: Optional[Dict[str, Any]] = None
    last_error: Optional[Exception] = None
    for model_name in model_candidates:
        try:
            response = client.models.generate_content(model=model_name, contents=[*parts, prompt])
            parsed = _extract_json_object(response.text or "{}")
            if not isinstance(parsed, dict):
                raise ValueError("Gemini Jugaad response was not a JSON object")
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini Jugaad guidance failed with model %s: %s", model_name, exc)
            continue

    if parsed is None:
        logger.info("Gemini Jugaad guidance unavailable, using heuristic fallback: %s", last_error)
        return _jugaad_fallback_plan(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            broken_analysis=broken_analysis,
            materials_analysis=materials_analysis,
            materials_note=materials_note,
        )

    step_by_step = _normalize_jugaad_list(parsed.get("step_by_step"))
    safety_notes = _normalize_jugaad_list(parsed.get("safety_notes"))
    materials_to_use = _normalize_jugaad_list(parsed.get("materials_to_use"))
    materials_to_avoid = _normalize_jugaad_list(parsed.get("materials_to_avoid"))
    when_to_stop = _normalize_jugaad_list(parsed.get("when_to_stop"))

    confidence = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "summary": str(parsed.get("summary") or "").strip() or "Temporary repair guidance generated.",
        "problem_read": str(parsed.get("problem_read") or "").strip() or f"{problem_title}: {problem_description}".strip(": "),
        "observed_broken_part": str(parsed.get("observed_broken_part") or broken_analysis.get("top_label") or "unclear").strip(),
        "observed_materials": str(parsed.get("observed_materials") or materials_analysis.get("top_label") or "unclear").strip(),
        "temporary_fix": str(parsed.get("temporary_fix") or "").strip() or "Use only external support and keep the repair temporary.",
        "step_by_step": step_by_step or [
            "Inspect the broken part externally without dismantling it.",
            "Use the available materials for temporary support or sealing only.",
            "Test carefully and stop if the repair is unstable.",
        ],
        "safety_notes": safety_notes or [
            "Keep the fix temporary and external.",
            "Escalate if any live electrical or pressurized system is involved.",
        ],
        "materials_to_use": materials_to_use or _normalize_jugaad_list(materials_analysis.get("tags") or []),
        "materials_to_avoid": materials_to_avoid or ["open live electrical parts", "forcing cracked structural components", "permanent unsafe hacks"],
        "when_to_stop": when_to_stop or ["The repair makes noise, leaks, sparks, or becomes unstable."],
        "needs_official_part": bool(parsed.get("needs_official_part", True)),
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "source": str(parsed.get("source") or f"gemini:{model_candidates[0] if model_candidates else DEFAULT_GEMINI_MODEL}"),
        "broken_analysis": broken_analysis,
        "materials_analysis": materials_analysis,
    }


def _infer_problem_topic(problem_title: str, problem_description: str, category: Optional[str], visual_tags: Optional[List[str]]) -> str:
    text = " ".join([
        problem_title or "",
        problem_description or "",
        category or "",
        " ".join(visual_tags or []),
    ]).lower()
    scores = {
        "water": sum(1 for keyword in _TOPIC_KEYWORDS["water"] if keyword in text),
        "health": sum(1 for keyword in _TOPIC_KEYWORDS["health"] if keyword in text),
        "infrastructure": sum(1 for keyword in _TOPIC_KEYWORDS["infrastructure"] if keyword in text),
        "agriculture": sum(1 for keyword in _TOPIC_KEYWORDS["agriculture"] if keyword in text),
        "digital": sum(1 for keyword in _TOPIC_KEYWORDS["digital"] if keyword in text),
    }
    topic = max(scores, key=scores.get)
    return topic if scores.get(topic, 0) > 0 else "general"


def _fallback_immediate_problem_guidance(
    *,
    problem_title: str,
    problem_description: str,
    category: Optional[str],
    visual_tags: Optional[List[str]],
    severity: Optional[str],
) -> Dict[str, Any]:
    topic = _infer_problem_topic(problem_title, problem_description, category, visual_tags)
    visual_tags = _normalize_jugaad_list(visual_tags or [])
    base_materials = ["rope", "cloth", "tape", "bucket", "bamboo", "rubber strip"]

    if topic == "water":
        actions = [
            "Lower the load or water pressure if there is any valve or tap control available.",
            "Use cloth, rubber strip, or tape only as an external temporary seal around small leaks.",
            "Brace loose pipes or pump parts with bamboo or wood so the joint is not carrying all the weight.",
            "Keep the repair area clean and dry to avoid contamination or slipping.",
        ]
        materials = ["rubber strip", "cloth", "tape", "bamboo support", "bucket", "rope"]
        safety = [
            "Do not use a temporary wrap if the pipe is under high pressure or the crack is spreading.",
            "Do not use open flames, glue on wet joints, or anything that blocks the water path.",
        ]
        stop = [
            "The leak becomes stronger after wrapping.",
            "The pipe or pump housing is split open.",
            "You can hear hissing, see splashing, or the support starts slipping.",
        ]
    elif topic == "health":
        actions = [
            "Keep the area clean and dry and remove standing water if that is contributing to the problem.",
            "Use mosquito nets, covered containers, and clean drinking water while waiting for medical support.",
            "If the issue is a sick person or multiple fever cases, contact a health worker quickly rather than trying a local fix.",
            "Track who is affected and when symptoms started so the coordinator has clear information.",
        ]
        materials = ["clean drinking water", "mosquito net", "covered container", "clean cloth", "thermometer if available"]
        safety = [
            "Do not delay medical help for fever, breathing trouble, severe pain, or dehydration.",
            "Do not rely on improvised remedies for suspected outbreak symptoms.",
        ]
        stop = [
            "Symptoms worsen, spread to others, or include high fever, breathing difficulty, or fainting.",
            "You suspect contaminated water or an outbreak source.",
        ]
    elif topic == "infrastructure":
        actions = [
            "Keep people away from the damaged area and mark it with cloth, stones, sticks, or rope.",
            "Use bamboo or wood only as an external brace to reduce movement, not as a permanent structural fix.",
            "If the surface is broken, cover sharp edges and reduce load until the right part arrives.",
            "Take a clear photo and note whether the damage is getting larger each day.",
        ]
        materials = ["rope", "cloth", "bamboo", "wood plank", "stones", "warning marker"]
        safety = [
            "Do not stand under unstable walls, poles, or beams.",
            "Do not touch exposed electrical wiring or support a load-bearing part by hand.",
        ]
        stop = [
            "The structure is bending, cracking, or making new noises.",
            "There is any live wire, heat, smoke, or visible instability.",
        ]
    elif topic == "agriculture":
        actions = [
            "Protect the crop or irrigation point from further damage with a simple external barrier or temporary channel.",
            "Use mud, cloth, or rope only for temporary water redirection or to keep livestock out.",
            "Avoid overwatering damaged lines; test flow in small amounts first.",
        ]
        materials = ["mud", "cloth", "rope", "bamboo", "bucket", "small stones"]
        safety = [
            "Do not use a temporary fix that floods the field or breaks a fragile line further.",
            "Do not handle pesticides or chemicals without proper protection.",
        ]
        stop = [
            "The channel or pipe is collapsing.",
            "Water is leaking faster after the fix.",
        ]
    elif topic == "digital":
        actions = [
            "Restart the device, unplug and reseat cables, and check the power source before assuming the device is dead.",
            "Use a clean cloth to remove dust and moisture from the outside only.",
            "If there is a loose connector, support it externally so it does not bend or pull out further.",
        ]
        materials = ["dry cloth", "tape", "charger", "spare cable", "power strip", "bamboo support"]
        safety = [
            "Do not open the device casing or touch live power connections.",
            "Do not continue using a hot, sparking, or wet electrical device.",
        ]
        stop = [
            "There is heat, smoke, or a burning smell.",
            "The device fails again immediately after a restart.",
        ]
    else:
        actions = [
            "Protect the damaged area from further stress or movement.",
            "Use the simplest external support you have to stabilize the part without opening it.",
            "Keep the repair temporary and reversible until the right part or technician arrives.",
        ]
        materials = base_materials
        safety = [
            "Only do external stabilization, not internal modification.",
            "Stop if the repair depends on force, heat, or live power.",
        ]
        stop = [
            "The part is structural, electrical, or pressurized.",
            "The temporary fix is slipping, cracking, or making the problem worse.",
        ]

    confidence = 0.42 + (0.05 * len(visual_tags)) + (0.08 if topic != "general" else 0.0)
    if severity == "HIGH":
        confidence = min(confidence, 0.72)
    if topic == "health":
        confidence = min(confidence, 0.68)

    return {
        "topic": topic,
        "summary": f"Immediate stabilization guidance for a {topic} issue.",
        "what_you_can_do_now": actions,
        "materials_to_find": materials,
        "safety_notes": safety,
        "when_to_stop": stop,
        "best_duration": "This is a temporary measure to buy time until the proper part or technician arrives.",
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "source": "heuristic",
        "visual_tags": visual_tags,
    }


def suggest_immediate_problem_actions(
    *,
    problem_title: str,
    problem_description: str,
    category: Optional[str] = None,
    visual_tags: Optional[List[str]] = None,
    severity: Optional[str] = None,
) -> Dict[str, Any]:
    """Provide immediate, locally available stabilization steps for the reporter."""
    topic = _infer_problem_topic(problem_title, problem_description, category, visual_tags)
    combined_text = " ".join([
        problem_title or "",
        problem_description or "",
        category or "",
        " ".join(visual_tags or []),
    ]).strip()

    if not _has_gemini_key():
        return _fallback_immediate_problem_guidance(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            visual_tags=visual_tags,
            severity=severity,
        )

    client = get_gemini_client()
    prompt = (
        "You are Gram Connect's instant stabilization assistant for the person reporting a problem.\n"
        "Give practical, temporary, safe actions that the reporter can do immediately with normal locally available materials.\n"
        "The goal is to keep the situation stable or usable for as long as possible until official help arrives.\n"
        "Do not suggest dangerous, permanent, electrical, pressurized, or medically risky repairs.\n"
        "If the issue is not something they can safely fix themselves, say so and focus on securing the area, preventing damage, and escalating.\n\n"
        f"Problem title: {problem_title}\n"
        f"Problem description: {problem_description}\n"
        f"Problem category: {category or 'unknown'}\n"
        f"Detected visual tags: {', '.join(visual_tags or []) or 'none'}\n"
        f"Priority/severity: {severity or 'unknown'}\n"
        f"Topic guess: {topic}\n"
        f"Combined context: {combined_text[:1500]}\n\n"
        "Return strict JSON only with these keys:\n"
        '  "topic": one of "water", "health", "infrastructure", "agriculture", "digital", or "general",\n'
        '  "summary": one concise sentence,\n'
        '  "what_you_can_do_now": array of 3 to 5 short, practical steps,\n'
        '  "materials_to_find": array of common local materials or tools,\n'
        '  "safety_notes": array of safety warnings,\n'
        '  "when_to_stop": array of signs the person should stop,\n'
        '  "best_duration": one sentence describing how long this temporary fix is meant to last,\n'
        '  "confidence": number from 0 to 1,\n'
        '  "source": "gemini".\n'
        "Keep the advice simple, field-practical, and temporary."
    )

    model_candidates = []
    for candidate in [DEFAULT_IMAGE_MODEL, DEFAULT_GEMINI_MODEL, "gemini-2.5-flash"]:
        candidate = str(candidate).strip()
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)

    last_error: Optional[Exception] = None
    parsed: Optional[Dict[str, Any]] = None
    for model_name in model_candidates:
        try:
            response = client.models.generate_content(model=model_name, contents=[prompt])
            parsed = _extract_json_object(response.text or "{}")
            if not isinstance(parsed, dict):
                raise ValueError("Gemini response was not a JSON object")
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini immediate guidance failed with model %s: %s", model_name, exc)
            continue

    if parsed is None:
        logger.info("Gemini immediate guidance unavailable, using heuristic fallback: %s", last_error)
        return _fallback_immediate_problem_guidance(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            visual_tags=visual_tags,
            severity=severity,
        )

    def _clean_list(value: Any) -> List[str]:
        return _normalize_jugaad_list(value)

    confidence = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    result = {
        "topic": str(parsed.get("topic") or topic).strip() or "general",
        "summary": str(parsed.get("summary") or "").strip() or "Temporary stabilization guidance generated.",
        "what_you_can_do_now": _clean_list(parsed.get("what_you_can_do_now")) or _fallback_immediate_problem_guidance(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            visual_tags=visual_tags,
            severity=severity,
        )["what_you_can_do_now"],
        "materials_to_find": _clean_list(parsed.get("materials_to_find")) or _fallback_immediate_problem_guidance(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            visual_tags=visual_tags,
            severity=severity,
        )["materials_to_find"],
        "safety_notes": _clean_list(parsed.get("safety_notes")) or _fallback_immediate_problem_guidance(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            visual_tags=visual_tags,
            severity=severity,
        )["safety_notes"],
        "when_to_stop": _clean_list(parsed.get("when_to_stop")) or _fallback_immediate_problem_guidance(
            problem_title=problem_title,
            problem_description=problem_description,
            category=category,
            visual_tags=visual_tags,
            severity=severity,
        )["when_to_stop"],
        "best_duration": str(parsed.get("best_duration") or "").strip() or "Temporary stabilization only until proper help arrives.",
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "source": str(parsed.get("source") or f"gemini:{model_candidates[0] if model_candidates else DEFAULT_GEMINI_MODEL}"),
        "visual_tags": _normalize_jugaad_list(visual_tags or []),
    }
    return result


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
        types = _get_gemini_types()
        if types is None:
            raise RuntimeError("Gemini types unavailable")
        
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
