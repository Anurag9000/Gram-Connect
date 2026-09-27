#!/usr/bin/env python3
"""Run one Nexus severity dataset group with one shared in-memory X/y matrix.

The four retained estimators are classical whole-estimator transactions, so this
worker does not falsely claim minibatch lockstep. It implements the useful part of
the dataset-cohort contract for classical science: one CSV read, one competitive-
zone filter/log transform, one shared NumPy feature matrix, then all model-family
fits/CV/SHAP extraction before the dataset is released.

AUTO is GPU-first for accelerator-capable XGBoost. LightGBM GPU is opt-in only when
the installed LightGBM build explicitly supports it (GRAM_LIGHTGBM_GPU=1).
cuML's accelerator is installed before importing sklearn where supported; unsupported
estimators and APIs retain sklearn CPU behavior. CPU mode is strict.
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

from dataset_cohort_runtime_entry_v3 import load_runtime  # noqa: E402
from gpu_optional_backends import activate_cuml_accel  # noqa: E402
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


def inspect_fitted_estimator(name: str, estimator: Any, *, gpu_requested: bool) -> dict[str, Any]:
    """Record fitted-estimator evidence without conflating it with CV execution.

    XGBoost exposes the *effective* device in the fitted Booster configuration.
    cuML's import hook can fall back per operation; a successful install does
    not establish where an sklearn fit ran. LightGBM's booster params record
    configuration, not a measured GPU operation.
    """
    if name == "XGBoost":
        config = json.loads(estimator.get_booster().save_config())
        effective = str(config.get("learner", {}).get("generic_param", {}).get("device", "unavailable"))
        on_cuda = effective.startswith("cuda") or effective.startswith("gpu")
        if gpu_requested and not on_cuda:
            raise RuntimeError(
                f"XGBoost requested CUDA but fitted Booster reports device={effective!r}"
            )
        return {
            "fitted_device": effective, "fit_device_evidence": "fitted_xgboost_booster_config",
            "gpu_fit_verified": on_cuda,
        }
    if name == "LightGBM":
        booster = getattr(estimator, "booster_", None)
        params = getattr(booster, "params", {}) if booster is not None else {}
        setting = str(params.get("device_type", params.get("device", "unavailable")))
        return {
            "fitted_device": setting, "fit_device_evidence": "fitted_lightgbm_booster_parameters",
            "gpu_fit_verified": False,
            "note": "configured GPU backend, not a measured GPU kernel",
        }
    return {
        "fitted_device": "unverified",
        "fit_device_evidence": "cuml_accel may dispatch or fall back per operation",
        "gpu_fit_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--severity", choices=tuple(SEVERITY), required=True)
    parser.add_argument("--backend", choices=("auto", "cpu", "gpu"), default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    runtime = load_runtime(ROOT)
    probe = runtime.detect_backend(args.backend)
    use_gpu = str(probe.selected_device).startswith("cuda")
    sklearn_acceleration = activate_cuml_accel(use_gpu)
    sev_int = SEVERITY[args.severity]
    source = ROOT / "data" / f"training_labels_{args.severity}.csv"
    if not source.is_file():
        raise SystemExit(f"missing severity training dataset: {source}")

    rows = nexus.read_csv(str(source))
    original = nexus._make_models
    nexus._make_models = lambda: _configured_factory(original, use_gpu=use_gpu)
    try:
        result = nexus.fit_severity(
            sev_int, rows,
            inspect_fit=lambda name, estimator: inspect_fitted_estimator(
                name, estimator, gpu_requested=use_gpu,
            ),
        )
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
        "sklearn_acceleration": sklearn_acceleration,
        "model_backends": {
            name: evidence["fitted_device"] if evidence["fit_status"] == "completed" else "failed"
            for name, evidence in result["model_execution"].items()
        },
        "model_execution_evidence": result["model_execution"],
        "failed_models": result["failed_models"],
        "all_candidate_fits_succeeded": result["all_candidate_fits_succeeded"],
        "backend_claim_boundary": (
            "XGBoost fitted Booster config verifies its effective device. "
            "LightGBM reports fitted configuration only. cuML hook installation does not "
            "prove GPU execution for individual sklearn fits or CV refits."
        ),
        "result": result,
        "model_training_executed": True,
    }
    _atomic_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
