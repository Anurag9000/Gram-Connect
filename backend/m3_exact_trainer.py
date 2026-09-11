"""Interruption-exact M3 recommender trainer for central OPF orchestration.

This is the authoritative training transaction for the retained M3 scientific
pipeline.  It preserves the original feature construction and GradientBoosting
model, but fixes the durability contract required by the account-wide controller:

* deterministic train/validation order;
* stage-exact warm-start continuation;
* current model + best model + best metric + patience state persisted together;
* configuration fingerprint validation before resume;
* atomic progress/best/final artifacts; and
* OPF checkpoint request acknowledgement only after the stage checkpoint exists.

The legacy ``m3_trainer.py`` remains available for compatibility, but the central
runner targets this exact implementation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import tempfile
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score

import m3_trainer as legacy
from training_control_runtime import acknowledge_checkpoint, checkpoint_requested


def _atomic_pickle(path: str | Path, payload: object) -> Path:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as stream:
            pickle.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _load_pickle(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        payload = pickle.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"checkpoint must contain a mapping: {path}")
    return payload


def _fingerprint(config: legacy.TrainingConfig) -> str:
    payload = {
        "proposals": str(Path(config.proposals).resolve()),
        "people": str(Path(config.people).resolve()),
        "pairs": str(Path(config.pairs).resolve()),
        "model_name": config.model_name,
        "village_locations": None if config.village_locations is None else str(Path(config.village_locations).resolve()),
        "village_distances": None if config.village_distances is None else str(Path(config.village_distances).resolve()),
        "distance_scale": float(config.distance_scale),
        "distance_decay": float(config.distance_decay),
        "n_estimators": int(config.n_estimators),
        "learning_rate": float(config.learning_rate),
        "subsample": float(config.subsample),
        "max_depth": int(config.max_depth),
        "validation_fraction": float(config.validation_fraction),
        "n_iter_no_change": int(config.n_iter_no_change),
        "tol": float(config.tol),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _prepare(config: legacy.TrainingConfig):
    for name, value in (
        ("proposals", config.proposals),
        ("people", config.people),
        ("pairs", config.pairs),
        ("village_locations", config.village_locations),
        ("village_distances", config.village_distances),
    ):
        if value and not os.path.exists(value):
            raise FileNotFoundError(f"missing {name}: {value}")

    props = legacy.read_csv_norm(config.proposals)
    people = legacy.read_csv_norm(config.people)
    pairs = legacy.read_csv_norm(config.pairs)
    village_names = legacy.load_village_names(config.village_locations)
    distance_lookup = legacy.load_distance_lookup(config.village_distances)

    proposal_locations: dict[str, str] = {}
    severity_levels: dict[str, int] = {}
    for row in props:
        proposal_id = legacy.get_any(row, ["proposal_id", "id"])
        if proposal_id is None:
            continue
        text = legacy.get_any(
            row,
            ["text", "proposal_text", "description", "body", "content"],
            "",
        )
        proposal_locations[proposal_id] = (
            legacy.extract_location(text, village_names) if village_names else ""
        )
        severity_levels[proposal_id] = legacy.estimate_severity(text)

    proposal_texts = [
        legacy.get_any(row, ["text", "proposal_text", "description", "body", "content"], "")
        for row in props
    ]
    people_texts = [legacy.get_any(row, ["text", "skills"], "") for row in people]
    proposal_model, _, backend_a = legacy.embed_texts(
        proposal_texts, model_name=config.model_name
    )
    people_model, _, backend_b = legacy.embed_texts(
        people_texts, model_name=config.model_name
    )
    if backend_a == "tfidf" or backend_b == "tfidf":
        shared, _, _ = legacy.embed_texts(
            proposal_texts + people_texts, model_name=config.model_name
        )
        proposal_model = shared
        people_model = shared
        backend = "tfidf"
    else:
        backend = "sentence-transformers"

    X, y = legacy.build_feature_matrix(
        props,
        people,
        pairs,
        proposal_model,
        people_model,
        backend,
        proposal_locations,
        severity_levels,
        distance_lookup,
        config.distance_scale,
        config.distance_decay,
    )
    if len(y) == 0:
        raise ValueError("no training pairs after normalization")

    rng = np.random.RandomState(42)
    order = rng.permutation(len(y))
    split_fraction = float(config.validation_fraction)
    if not 0.0 < split_fraction < 1.0:
        raise ValueError("validation_fraction must be in (0, 1)")
    split = max(1, min(len(order), int((1.0 - split_fraction) * len(order))))
    train_index, validation_index = order[:split], order[split:]
    return (
        X[train_index],
        y[train_index],
        X[validation_index],
        y[validation_index],
        proposal_model,
        people_model,
        backend,
        order,
    )


def train_exact(config: legacy.TrainingConfig) -> float:
    (
        Xtr,
        ytr,
        Xva,
        yva,
        proposal_model,
        people_model,
        backend,
        order,
    ) = _prepare(config)
    output = Path(config.out).resolve()
    progress_path = output.with_name(f"{output.stem}.exact.progress.pkl")
    best_path = output.with_name(f"{output.stem}.exact.best.pkl")
    fingerprint = _fingerprint(config)

    stage = 0
    best_stage = 0
    best_score = float("-inf")
    no_improve = 0
    best_model = None
    model = None

    if config.resume_from_checkpoint:
        state = _load_pickle(progress_path)
        if state is not None:
            if state.get("config_fingerprint") != fingerprint:
                raise RuntimeError(
                    "existing M3 exact checkpoint belongs to a different training configuration"
                )
            model = state.get("model")
            best_model = state.get("best_model")
            stage = int(state.get("stage", 0))
            best_stage = int(state.get("best_stage", 0))
            best_score = float(state.get("best_score", float("-inf")))
            no_improve = int(state.get("no_improve", 0))
            saved_order = np.asarray(state.get("permutation"), dtype=np.int64)
            if not np.array_equal(saved_order, order):
                raise RuntimeError("deterministic M3 train/validation order drifted")

    if model is None:
        model = GradientBoostingClassifier(
            random_state=42,
            warm_start=True,
            n_estimators=1,
            learning_rate=config.learning_rate,
            subsample=config.subsample,
            max_depth=config.max_depth,
        )
    else:
        model.set_params(warm_start=True)

    max_estimators = max(1, int(config.n_estimators))
    patience = max(1, int(config.n_iter_no_change))
    for current_stage in range(stage + 1, max_estimators + 1):
        model.set_params(n_estimators=current_stage, warm_start=True)
        model.fit(Xtr, ytr)

        if len(Xva) and len(np.unique(yva)) > 1:
            score = float(roc_auc_score(yva, model.predict_proba(Xva)[:, 1]))
        else:
            score = float(model.score(Xtr, ytr))

        if score > best_score + float(config.tol):
            best_score = score
            best_stage = current_stage
            best_model = copy.deepcopy(model)
            no_improve = 0
        else:
            no_improve += 1

        state = {
            "schema_version": 1,
            "config_fingerprint": fingerprint,
            "model": model,
            "best_model": best_model,
            "stage": current_stage,
            "best_stage": best_stage,
            "best_score": best_score,
            "no_improve": no_improve,
            "permutation": np.asarray(order, dtype=np.int64),
            "backend": backend,
            "restart_exact": True,
        }
        saved = _atomic_pickle(progress_path, state)
        if current_stage == best_stage:
            _atomic_pickle(best_path, state)

        if checkpoint_requested():
            acknowledge_checkpoint(
                checkpoint=saved,
                metadata={
                    "trainer": "gram_m3_exact",
                    "stage": current_stage,
                    "best_stage": best_stage,
                    "best_score": best_score,
                },
            )

        if no_improve >= patience:
            break

    if best_model is None:
        best_model = copy.deepcopy(model)
        best_stage = int(getattr(model, "n_estimators", stage))
        best_score = float(model.score(Xtr, ytr))

    final_payload = {
        "schema_version": 1,
        "model": best_model,
        "backend": backend,
        "prop_model": proposal_model,
        "people_model": people_model,
        "distance_scale": config.distance_scale,
        "distance_decay": config.distance_decay,
        "n_estimators_used": int(getattr(best_model, "n_estimators", best_stage)),
        "best_stage": best_stage,
        "best_score": best_score,
        "config_fingerprint": fingerprint,
        "restart_exact": True,
        "early_stopping": {
            "patience": patience,
            "min_delta": float(config.tol),
            "metric": "validation_roc_auc",
        },
        "checkpoint_paths": {
            "progress": progress_path.as_posix(),
            "best": best_path.as_posix(),
        },
    }
    _atomic_pickle(output, final_payload)
    return float(best_score if math.isfinite(best_score) else float("nan"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--people", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument(
        "--out",
        default=str((legacy.get_repo_paths().runtime_dir / "canonical_model.pkl").resolve()),
    )
    parser.add_argument("--model_name", default="sentence-transformers/all-MiniLM-L6-v2")
    dataset_root = str(legacy.get_repo_paths().data_dir.resolve())
    parser.add_argument(
        "--village_locations",
        default=os.path.join(dataset_root, "village_locations.csv"),
    )
    parser.add_argument(
        "--village_distances",
        default=os.path.join(dataset_root, "village_distances.csv"),
    )
    parser.add_argument("--distance_scale", type=float, default=50.0)
    parser.add_argument("--distance_decay", type=float, default=30.0)
    parser.add_argument("--n_estimators", type=int, default=600)
    parser.add_argument("--learning_rate", type=float, default=0.03)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--max_depth", type=int, default=3)
    parser.add_argument("--validation_fraction", type=float, default=0.2)
    parser.add_argument("--n_iter_no_change", type=int, default=20)
    parser.add_argument("--tol", type=float, default=1e-4)
    parser.add_argument("--resume_from_checkpoint", action="store_true", default=True)
    parser.add_argument(
        "--no-resume_from_checkpoint",
        dest="resume_from_checkpoint",
        action="store_false",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = legacy.TrainingConfig(
        proposals=args.proposals,
        people=args.people,
        pairs=args.pairs,
        out=args.out,
        model_name=args.model_name,
        village_locations=args.village_locations,
        village_distances=args.village_distances,
        distance_scale=args.distance_scale,
        distance_decay=args.distance_decay,
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        subsample=args.subsample,
        max_depth=args.max_depth,
        validation_fraction=args.validation_fraction,
        n_iter_no_change=args.n_iter_no_change,
        tol=args.tol,
        resume_from_checkpoint=args.resume_from_checkpoint,
        checkpoint_every=1,
    )
    score = train_exact(config)
    print(json.dumps({"status": "complete", "validation_roc_auc": score}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
