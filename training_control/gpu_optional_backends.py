"""Optional GPU acceleration must be installed before sklearn is imported."""
from __future__ import annotations

import importlib
import os
import sys
import warnings


def activate_cuml_accel(use_gpu: bool) -> dict[str, bool | str]:
    """Install RAPIDS' supported sklearn accelerators, never claim all estimators GPU."""
    if not use_gpu:
        return {"enabled": False, "reason": "cpu_admitted"}
    if os.environ.get("GRAM_DISABLE_CUML_ACCEL", "").strip().lower() in {"1", "true", "yes"}:
        return {"enabled": False, "reason": "disabled_by_operator"}
    if any(name in sys.modules for name in ("sklearn", "umap", "hdbscan")):
        warnings.warn("cuML acceleration skipped: target estimator imported first",
                      RuntimeWarning, stacklevel=2)
        return {"enabled": False, "reason": "target_already_imported"}
    try:
        accelerator = importlib.import_module("cuml.accel")
        accelerator.install()
    except ImportError:
        return {"enabled": False, "reason": "cuml_accel_not_installed"}
    except Exception as exc:
        warnings.warn(f"cuML accelerator activation failed: {exc}",
                      RuntimeWarning, stacklevel=2)
        return {"enabled": False, "reason": "accelerator_install_failed"}
    return {"enabled": True, "reason": "installed_before_sklearn_import"}
