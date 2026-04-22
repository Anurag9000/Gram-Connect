import os
from typing import Optional

from generate_canonical_dataset import main as generate_canonical_dataset
from m3_trainer import TrainingConfig, train_model


def should_bootstrap_models() -> bool:
    if os.getenv("GRAM_CONNECT_SKIP_BOOTSTRAP", "").strip().lower() in {"1", "true", "yes"}:
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def ensure_canonical_dataset() -> None:
    generate_canonical_dataset()


def ensure_trained_model(
    *,
    model_path: str,
    proposals: str,
    people: str,
    pairs: str,
    village_locations: str,
    village_distances: str,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    force: bool = False,
) -> str:
    if not force and os.path.exists(model_path):
        return model_path

    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    train_model(
        TrainingConfig(
            proposals=proposals,
            people=people,
            pairs=pairs,
            out=model_path,
            model_name=model_name,
            village_locations=village_locations,
            village_distances=village_distances,
        )
    )
    return model_path

