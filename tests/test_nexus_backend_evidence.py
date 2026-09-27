"""Source-level regression tests for fit-device evidence and candidate failures."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from backend import fit_nexus_weights as nexus
from training_control.run_nexus_severity_group_v1 import inspect_fitted_estimator


class FakeXGB:
    def __init__(self, device: str):
        self.device = device
    def get_booster(self):
        return SimpleNamespace(save_config=lambda: json.dumps({
            "learner": {"generic_param": {"device": self.device}}
        }))


def test_xgboost_effective_cuda_device_is_reported():
    actual = inspect_fitted_estimator("XGBoost", FakeXGB("cuda:0"), gpu_requested=True)
    assert actual["fitted_device"] == "cuda:0"
    assert actual["gpu_fit_verified"] is True


def test_xgboost_silent_cpu_fallback_is_rejected():
    with pytest.raises(RuntimeError, match="requested CUDA"):
        inspect_fitted_estimator("XGBoost", FakeXGB("cpu"), gpu_requested=True)
    cpu = inspect_fitted_estimator("XGBoost", FakeXGB("cpu"), gpu_requested=False)
    assert cpu["gpu_fit_verified"] is False


def test_other_gpu_claims_remain_unverified_without_profiling():
    lgb = SimpleNamespace(booster_=SimpleNamespace(params={"device_type": "gpu"}))
    got = inspect_fitted_estimator("LightGBM", lgb, gpu_requested=True)
    assert got["fitted_device"] == "gpu"
    assert got["gpu_fit_verified"] is False
    sklearn = inspect_fitted_estimator("LogReg", object(), gpu_requested=True)
    assert sklearn["gpu_fit_verified"] is False


def test_all_failed_candidates_raise_instead_of_fabricating_best_model():
    class Broken:
        def fit(self, *args):
            raise RuntimeError("GPU runtime unavailable")
    with mock.patch.object(nexus, "_make_models", return_value={"LogReg": Broken()}):
        rows = [{"domain_score": "0.5", "will_score": "0.5", "avail_score": "0.5",
                 "prox_score": "0.5", "fresh_score": "0.5", "label": "1"}]
        with pytest.raises(RuntimeError, match="all Nexus severity candidates failed"):
            nexus.fit_severity(0, rows)


def test_failed_candidate_and_unverified_cv_are_machine_readable():
    class Good:
        def fit(self, *args):
            return self
    class Broken:
        def fit(self, *args):
            raise RuntimeError("driver unavailable")
    row = {"domain_score": "0.5", "will_score": "0.5", "avail_score": "0.5",
           "prox_score": "0.5", "fresh_score": "0.5", "label": "1"}
    with mock.patch.object(nexus, "_make_models", return_value={"LogReg": Good(), "XGBoost": Broken()}), \
         mock.patch.object(nexus, "_cv_auc", return_value=np.asarray([0.75] * 5)), \
         mock.patch.object(nexus, "_weights_from_shap", return_value={name: 1.0 for name in nexus.FACTORS}):
        result = nexus.fit_severity(0, [row], inspect_fit=lambda name, model: {
            "fitted_device": "cpu", "gpu_fit_verified": False,
        })
    assert result["best_model"] == "LogReg"
    assert result["model_execution"]["LogReg"]["cross_validation_gpu_verified"] is False
    assert result["model_execution"]["XGBoost"]["fit_status"] == "failed"
    assert result["all_candidate_fits_succeeded"] is False
