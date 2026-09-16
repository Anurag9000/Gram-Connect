#!/usr/bin/env python3
"""One-command exhaustive Gram-Connect dataset-group training controller.

The retained v1 catalog remains the logical scientific inventory.  Physical v2
execution is dataset-centric:

* HIGH, LOW and NORMAL Nexus supervision are three single-dataset groups.  Each
  parent materializes its feature matrix once and runs LogisticRegression,
  RandomForest, XGBoost and LightGBM whole-estimator transactions against it.
* tied four-family groups are deterministically ordered by dataset key;
* their outputs are merged back to the legacy fitted_weights_per_severity.json;
* M3 consumes proposals/people/pairs/village sources and runs last as the overlap
  group, preserving stage-exact GradientBoosting resume and ROC-AUC early stopping.

Classical estimators are not falsely described as minibatch trainers: shared-batch
lockstep is inapplicable to their monolithic ``fit`` calls.  The central contract
still requires any future batch-steppable model to use the cohort runtime.  CPU-only
and GPU-first variants share the same science; AUTO prefers a usable CUDA backend.
SentenceTransformer and XGBoost can use CUDA, while sklearn estimators remain CPU.
Resource admission, pressure monitoring, retry/relaunch and GPU assignment remain
in the exact pinned OPF_ADP-derived controller v37.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Anurag9000/Gram-Connect"
CONTROLLER_COMMIT = "fd34a95d18892df7fb14d1efbb99076a7810fb91"
CONTROLLER_BLOB = "05ef472b29933f18e956c69dfb7e543921ddaff5"
CONTROLLER_URL = (
    f"https://raw.githubusercontent.com/Anurag9000/RigorousRAG/{CONTROLLER_COMMIT}/"
    "tools/universal_training_controller_entry.py"
)
CATALOG_PATH = "training_control/gram_scientific_job_catalog_v2.py"

PROFILE = {
    "repository": REPOSITORY,
    "scientific_authority": CATALOG_PATH,
    "scientific_authority_version": 2,
    "logical_scientific_authority": "training_control/gram_scientific_job_catalog_v1.py",
    "job_catalog": {"path": CATALOG_PATH, "function": "iter_jobs", "args": [], "kwargs": {}},
    "preferred_training_entrypoints": [
        "training_control/run_nexus_severity_group_v1.py",
        "training_control/run_m3_overlap_group_v1.py",
    ],
    "preferred_dataset_entrypoints": [
        "backend/generate_canonical_dataset.py",
        "backend/generate_training_labels.py",
    ],
    "dynamic_registry_covers": [
        "backend/*.py",
        "data/*.csv",
        "training_control/gram_scientific_job_catalog_v1.py",
        "training_control/gram_scientific_job_catalog_v2.py",
        "training_control/run_nexus_severity_group_v1.py",
        "training_control/merge_nexus_severity_groups_v1.py",
        "training_control/run_m3_overlap_group_v1.py",
        "training_control/dataset_cohort_runtime_entry.py",
    ],
    "ignore_entrypoints": [
        "run_all_training.py",
        "scripts/audit_gram_scientific_authority_v1.py",
        "backend/training_control_runtime.py",
        "training_control/merge_nexus_severity_groups_v1.py",
    ],
    "strict_coverage": True,
    "require_native_resume": True,
    "require_exact_resume": True,
    "require_training_exact_resume": True,
    "require_training_early_stopping": True,
    "require_well_formed_training_exemptions": True,
    "require_dag_enforcement": True,
    "require_model_surface_accounting": True,
    "require_workload_surface_accounting": True,
    "require_literal_opf_mechanism_parity": True,
    "require_registry_member_accounting": True,
    "require_dynamic_registry_accounting": True,
    "require_scientific_component_config_accounting": True,
    "require_declared_combination_accounting": True,
    "require_scientific_ontology_accounting": True,
    "require_declarative_scientific_source_accounting": True,
    "require_extended_scientific_component_accounting": True,
    "require_full_scientific_choice_accounting": True,
    "require_role_paradigm_protocol_accounting": True,
    "require_existing_job_targets": True,
    "require_source_proven_training_exact_resume": True,
    "require_source_proven_training_early_stopping": True,
    "require_all_retained_trainable_source_reachability": True,
    "auto_console_training_jobs": False,
    "auto_console_subcommand_jobs": False,
    "require_dataset_cohort_execution": True,
    "require_cpu_gpu_backend_variants": True,
    "require_shared_batch_views": True,
    "require_uniform_cohort_batch_size": True,
    "require_cohort_exact_resume": True,
    "require_lossless_sample_stream_compatibility": True,
    "require_pressure_residency_windows_when_source_safe": True,
    "classical_batch_lockstep_applicable": False,
    "classical_shared_dataset_materialization": True,
    "overlap_group_required_last": True,
}


def _blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def main() -> int:
    catalog = ROOT / CATALOG_PATH
    if not catalog.is_file():
        raise RuntimeError(f"Gram physical scientific authority is missing: {catalog}")
    cache = ROOT / ".training_control" / "universal_training_controller_entry.py"
    if not cache.is_file() or _blob(cache.read_bytes()) != CONTROLLER_BLOB:
        payload = urllib.request.urlopen(CONTROLLER_URL, timeout=60).read()
        actual = _blob(payload)
        if actual != CONTROLLER_BLOB:
            raise RuntimeError(f"Pinned controller checksum mismatch: {actual} != {CONTROLLER_BLOB}")
        _atomic(cache, payload)
    profile_path = ROOT / ".training_control" / "gram_scientific_v2_cohort_v37.json"
    _atomic(profile_path, (json.dumps(PROFILE, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    env = os.environ.copy()
    env.pop("TRAINING_CONTROL_PROFILE", None)
    env["TRAINING_CONTROL_PROFILE_FILE"] = str(profile_path)
    env["TRAINING_CONTROL_REPO_ROOT"] = str(ROOT)
    env.setdefault("TRAINING_CONTROL_TERMINATION_GRACE_SEC", "30")
    return subprocess.call([sys.executable, str(cache), *sys.argv[1:]], cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
