import os
from pathlib import Path
from typing import Iterable

from path_utils import get_repo_paths


def _iter_env_files() -> Iterable[Path]:
    paths = get_repo_paths()
    return (
        paths.repo_root / ".env.local",
        paths.repo_root / ".env",
        paths.backend_dir / ".env.local",
        paths.backend_dir / ".env",
    )


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_local_env() -> None:
    force_override = {"GEMINI_API_KEY", "GOOGLE_API_KEY"}
    for env_file in _iter_env_files():
        if not env_file.exists() or not env_file.is_file():
            continue

        try:
            for raw_line in env_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                if key in os.environ and key not in force_override:
                    continue

                os.environ[key] = _strip_quotes(value.strip())
        except Exception:
            # Ignore malformed local env files; shell exports still win.
            continue
