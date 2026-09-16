"""
embeddings.py
- Provides ``embed_texts(texts, model_name)`` using sentence-transformers.
- AUTO is GPU-first when CUDA is usable; CPU mode is strict and hides CUDA use.
- Falls back to TF-IDF when sentence-transformers itself is unavailable, preserving
  the historical scientific fallback.
"""
from __future__ import annotations

import os
from typing import List, Tuple

import numpy as np


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def requested_device() -> str:
    """Resolve the central runner backend without silently violating CPU-only mode."""
    if _truthy(os.environ.get("CPU_ONLY")) or _truthy(os.environ.get("TRAINING_CONTROL_CPU_ONLY")):
        return "cpu"
    mode = str(os.environ.get("TRAINING_CONTROL_BACKEND", "auto")).strip().lower() or "auto"
    if mode not in {"auto", "cpu", "gpu"}:
        raise ValueError(f"unsupported TRAINING_CONTROL_BACKEND={mode!r}")
    if mode == "cpu":
        return "cpu"
    try:
        import torch
        available = bool(torch.cuda.is_available() and torch.cuda.device_count() > 0)
    except Exception:
        available = False
    if mode == "gpu" and not available:
        raise RuntimeError("Gram GPU backend requested but PyTorch CUDA is unavailable")
    if available:
        index = str(os.environ.get("TRAINING_CONTROL_GPU_INDEX", os.environ.get("GPU_DEVICE_INDEX", "0"))).strip() or "0"
        return f"cuda:{index}"
    return "cpu"


def embed_texts(
    texts: List[str],
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
) -> Tuple[object, np.ndarray, str]:
    """Return ``(model_or_vectorizer, embeddings, backend)``.

    ``backend`` is ``sentence-transformers`` or ``tfidf``.  SentenceTransformer
    receives the central CPU/CUDA decision explicitly; it is not allowed to choose a
    hidden CUDA device in CPU-only mode.
    """
    texts = [t if isinstance(t, str) else "" for t in texts]

    if not model_name.lower().startswith("tfidf"):
        try:
            from sentence_transformers import SentenceTransformer
            device = requested_device()
            model = SentenceTransformer(model_name, device=device)
            embs = np.asarray(
                model.encode(
                    texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    device=device,
                )
            )
            return model, embs, "sentence-transformers"
        except RuntimeError:
            # Explicit GPU requests are fail-closed rather than being silently
            # reinterpreted as a CPU/TF-IDF experiment.
            if str(os.environ.get("TRAINING_CONTROL_BACKEND", "auto")).lower() == "gpu":
                raise
        except Exception:
            pass

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, stop_words="english")
    X = vec.fit_transform([t.lower() for t in texts])
    X = normalize(X)
    return vec, X, "tfidf"


def embed_with(model_or_vec, texts: List[str], backend: str) -> "np.ndarray":
    texts = [t if isinstance(t, str) else "" for t in texts]
    if backend == "sentence-transformers":
        device = requested_device()
        embs = model_or_vec.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            device=device,
        )
        return np.asarray(embs)

    from sklearn.preprocessing import normalize

    X = model_or_vec.transform([t.lower() for t in texts])
    return normalize(X)


def cosine_sim(a, b):
    """Cosine similarity for dense or sparse matrices."""
    from sklearn.metrics.pairwise import cosine_similarity

    return cosine_similarity(a, b)
