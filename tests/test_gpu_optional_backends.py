"""No-CUDA-required contracts for Gram's optional estimator acceleration."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from training_control import gpu_optional_backends as gpu


def test_cpu_never_loads_rapids():
    with mock.patch.object(gpu.importlib, "import_module") as importer:
        assert gpu.activate_cuml_accel(False) == {"enabled": False, "reason": "cpu_admitted"}
    importer.assert_not_called()


def test_cuml_install_hook_is_called_for_admitted_cuda(monkeypatch):
    monkeypatch.delenv("GRAM_DISABLE_CUML_ACCEL", raising=False)
    fake = SimpleNamespace(install=mock.Mock())
    with mock.patch.object(gpu, "sys", SimpleNamespace(modules={})), \
         mock.patch.object(gpu.importlib, "import_module", return_value=fake):
        result = gpu.activate_cuml_accel(True)
    assert result["enabled"] is True
    fake.install.assert_called_once_with()


def test_import_order_prevents_false_success():
    with mock.patch.object(gpu, "sys", SimpleNamespace(modules={"sklearn": object()})):
        result = gpu.activate_cuml_accel(True)
    assert result == {"enabled": False, "reason": "target_already_imported"}


def test_missing_accelerator_falls_back_to_sklearn(monkeypatch):
    monkeypatch.delenv("GRAM_DISABLE_CUML_ACCEL", raising=False)
    with mock.patch.object(gpu, "sys", SimpleNamespace(modules={})), \
         mock.patch.object(gpu.importlib, "import_module", side_effect=ImportError):
        result = gpu.activate_cuml_accel(True)
    assert result == {"enabled": False, "reason": "cuml_accel_not_installed"}
