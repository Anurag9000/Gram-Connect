import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class RepoPaths:
    repo_root: Path
    backend_dir: Path
    data_dir: Path
    runtime_dir: Path


def get_repo_paths() -> RepoPaths:
    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parent
    data_dir = repo_root / "data"
    runtime_dir = backend_dir / "runtime_data"
    return RepoPaths(
        repo_root=repo_root,
        backend_dir=backend_dir,
        data_dir=data_dir,
        runtime_dir=runtime_dir,
    )


def _existing_path(candidates: Iterable[Path]) -> Optional[str]:
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return None


def _env_path(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return os.path.abspath(os.path.expanduser(value))
    return None


def resolve_model_path() -> str:
    paths = get_repo_paths()
    env_value = _env_path("GRAM_CONNECT_MODEL_PATH", "MODEL_PATH")
    if env_value:
        return env_value
    return str((paths.backend_dir / "model.pkl").resolve())


def resolve_people_csv() -> str:
    paths = get_repo_paths()
    env_value = _env_path("GRAM_CONNECT_PEOPLE_CSV", "PEOPLE_CSV")
    if env_value:
        return env_value

    resolved = _existing_path(
        [
            paths.data_dir / "people.csv",
            paths.backend_dir / "people.csv",
            paths.backend_dir / "people_2.csv",
        ]
    )
    if resolved:
        return resolved
    return str((paths.data_dir / "people.csv").resolve())


def resolve_proposals_csv() -> str:
    paths = get_repo_paths()
    env_value = _env_path("GRAM_CONNECT_PROPOSALS_CSV", "PROPOSALS_CSV")
    if env_value:
        return env_value

    resolved = _existing_path(
        [
            paths.data_dir / "proposals.csv",
            paths.backend_dir / "proposals.csv",
            paths.backend_dir / "proposals_2.csv",
            paths.runtime_dir / "proposals.csv",
        ]
    )
    if resolved:
        return resolved
    return str((paths.runtime_dir / "proposals.csv").resolve())


def resolve_pairs_csv() -> str:
    paths = get_repo_paths()
    env_value = _env_path("GRAM_CONNECT_PAIRS_CSV", "PAIRS_CSV")
    if env_value:
        return env_value

    resolved = _existing_path(
        [
            paths.data_dir / "pairs.csv",
            paths.backend_dir / "pairs.csv",
        ]
    )
    if resolved:
        return resolved
    return str((paths.data_dir / "pairs.csv").resolve())


def resolve_village_locations_csv() -> str:
    paths = get_repo_paths()
    env_value = _env_path("GRAM_CONNECT_VILLAGE_LOCATIONS_CSV", "VILLAGE_LOCATIONS_CSV")
    if env_value:
        return env_value

    resolved = _existing_path(
        [
            paths.data_dir / "village_locations.csv",
            paths.backend_dir / "village_locations.csv",
        ]
    )
    if resolved:
        return resolved
    return str((paths.data_dir / "village_locations.csv").resolve())


def resolve_distance_csv() -> str:
    paths = get_repo_paths()
    env_value = _env_path("GRAM_CONNECT_DISTANCE_CSV", "DISTANCE_CSV")
    if env_value:
        return env_value

    resolved = _existing_path(
        [
            paths.data_dir / "village_distances.csv",
            paths.backend_dir / "village_distances.csv",
        ]
    )
    if resolved:
        return resolved
    return str((paths.data_dir / "village_distances.csv").resolve())


def ensure_runtime_dir() -> str:
    runtime_dir = get_repo_paths().runtime_dir
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return str(runtime_dir.resolve())
