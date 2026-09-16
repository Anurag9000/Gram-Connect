#!/usr/bin/env python3
"""Run one Nexus severity dataset group with one shared in-memory X/y matrix.

The four retained estimators are classical whole-estimator transactions, so this
worker does not falsely claim minibatch lockstep. It implements the useful part of
the dataset-cohort contract for classical science: one CSV read, one competitive-
zone filter/log transform, one shared NumPy feature matrix, then all model-family
fits/CV/SHAP extraction before the dataset is released.

AUTO is GPU-first for accelerator-capable XGBoost. LightGBM GPU is opt-in only when
the installed LightGBM build explicitly supports it (GRAM_LIGHTGBM_GPU=1); sklearn
LogReg/RandomForest remain CPU estimators by design. CPU mode is strict.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CONTROL = ROOT / "training_control"
for value in (BACKEND, CONTROL):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from dataset_cohort_runtime_entry import load_runtime  # noqa: E402
import fit_nexus_weights as nexus  # noqa: E402

SCHEMA = "gram-nexus-severity-group/v1"
SEVERITY = {"low": 0, "normal": 1, "high": 2}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _configured_factory(original: Callable[[], dict[str, Any]], *, use_gpu: bool):
    models = original()
    if use_gpu:
        xgb = models.get("XGBoost")
        if xgb is not None:
            xgb.set_params(device="cuda")
        if _truthy(os.environ.get("GRAM_LIGHTGBM_GPU")):
            lgb = models.get("LightGBM")
            if lgb is not None:
                lgb.set_params(device_type="gpu")
    return models


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--severity", choices=tuple(SEVERITY), required=True)
    parser.add_argument("--backend", choices=("auto", "cpu", "gpu"), default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    runtime = load_runtime(ROOT)
    probe = runtime.detect_backend(args.backend)
    use_gpu = str(probe.selected_device).startswith("cuda")
    sev_int = SEVERITY[args.severity]
    source = ROOT / "data" / f"training_labels_{args.severity}.csv"
    if not source.is_file():
        raise SystemExit(f"missing severity training dataset: {source}")

    rows = nexus.read_csv(str(source))
    original = nexus._make_models
    nexus._make_models = lambda: _configured_factory(original, use_gpu=use_gpu)
    try:
        result = nexus.fit_severity(sev_int, rows)
    finally:
        nexus._make_models = original

    output = args.output or Path(f"artifacts/training_control/nexus_{args.severity}_group_v1.json")
    output = output if output.is_absolute() else ROOT / output
    payload = {
        "schema": SCHEMA,
        "repository": "Anurag9000/Gram-Connect",
        "dataset": source.as_posix(),
        "severity": args.severity,
        "severity_id": sev_int,
        "requested_backend": args.backend,
        "selected_backend": probe.selected_device,
        "shared_dataset_materialization": True,
        "classical_transaction_semantics": "whole-estimator fit/CV; no false minibatch lockstep",
        "model_backends": {
            "LogReg": "cpu",
            "RandomForest": "cpu",
            "XGBoost": "gpu" if use_gpu else "cpu",
            "LightGBM": "gpu" if use_gpu and _truthy(os.environ.get("GRAM_LIGHTGBM_GPU")) else "cpu",
        },
        "result": result,
        "model_training_executed": True,
    }
    _atomic_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
