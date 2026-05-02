import os
import sys
import types

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_optional_module_stubs() -> None:
    if "sentence_transformers" not in sys.modules:
        stubs = types.ModuleType("sentence_transformers")

        class SentenceTransformer:  # pragma: no cover - test shim
            def __init__(self, *args, **kwargs):
                self.model_name = args[0] if args else kwargs.get("model_name", "stub")

            def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True):
                import hashlib
                import numpy as np

                rows = []
                for text in texts:
                    digest = hashlib.sha256(str(text).encode("utf-8")).digest()
                    values = [(digest[index] / 255.0) for index in range(8)]
                    rows.append(values)
                return np.asarray(rows, dtype=float)

            def transform(self, texts):  # pragma: no cover - test shim
                return self.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

        stubs.SentenceTransformer = SentenceTransformer
        sys.modules["sentence_transformers"] = stubs

    if "whisper" not in sys.modules:
        whisper = types.ModuleType("whisper")

        class _WhisperModel:  # pragma: no cover - test shim
            def transcribe(self, audio_path):
                return {"text": f"stub transcription for {audio_path}", "language": "en"}

        def load_model(*args, **kwargs):  # pragma: no cover - test shim
            return _WhisperModel()

        whisper.load_model = load_model
        sys.modules["whisper"] = whisper

    if "torch" not in sys.modules:
        torch = types.ModuleType("torch")

        class _Tensor:  # pragma: no cover - test shim
            def __init__(self, values):
                self.values = values

            def to(self, *args, **kwargs):
                return self

            def softmax(self, dim=-1):
                import math
                import numpy as np

                arr = np.asarray(self.values, dtype=float)
                exp = np.exp(arr - np.max(arr, axis=dim, keepdims=True))
                return _Tensor(exp / exp.sum(axis=dim, keepdims=True))

            def cpu(self):
                return self

            def numpy(self):
                import numpy as np

                return np.asarray(self.values, dtype=float)

        class _Cuda:  # pragma: no cover - test shim
            @staticmethod
            def is_available():
                return False

        class _NoGrad:  # pragma: no cover - test shim
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def tensor(values, *args, **kwargs):  # pragma: no cover - test shim
            return _Tensor(values)

        def zeros(shape, *args, **kwargs):  # pragma: no cover - test shim
            import numpy as np

            return _Tensor(np.zeros(shape, dtype=float))

        torch.tensor = tensor
        torch.Tensor = _Tensor
        torch.zeros = zeros
        torch.no_grad = _NoGrad
        torch.cuda = _Cuda()
        sys.modules["torch"] = torch

    if "PIL" not in sys.modules:
        pil = types.ModuleType("PIL")
        image_mod = types.ModuleType("PIL.Image")

        class _Image:  # pragma: no cover - test shim
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def convert(self, *args, **kwargs):
                return self

        def open_stub(*args, **kwargs):  # pragma: no cover - test shim
            return _Image()

        image_mod.open = open_stub
        pil.Image = image_mod
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = image_mod

    if "google" not in sys.modules:
        google_pkg = types.ModuleType("google")
        google_pkg.__path__ = []  # type: ignore[attr-defined]
        genai_mod = types.ModuleType("google.genai")
        types_mod = types.ModuleType("google.genai.types")

        class _Part:  # pragma: no cover - test shim
            @staticmethod
            def from_bytes(*, data, mime_type):
                return {"data": data, "mime_type": mime_type}

        class _Models:  # pragma: no cover - test shim
            def generate_content(self, *args, **kwargs):
                raise RuntimeError("google.genai stub in tests should be patched")

        class _Client:  # pragma: no cover - test shim
            def __init__(self, *args, **kwargs):
                self.models = _Models()

        types_mod.Part = _Part
        genai_mod.Client = _Client
        genai_mod.types = types_mod
        google_pkg.genai = genai_mod
        sys.modules["google"] = google_pkg
        sys.modules["google.genai"] = genai_mod
        sys.modules["google.genai.types"] = types_mod


_install_optional_module_stubs()
import api_server


@pytest.fixture(autouse=True)
def isolated_runtime_state():
    api_server.reset_runtime_state()
    yield
    api_server.reset_runtime_state()
