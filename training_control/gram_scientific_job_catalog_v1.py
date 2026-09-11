#!/usr/bin/env python3
"""Repository-owned executable scientific DAG for Gram-Connect.

The catalog exposes the retained scientific transactions independently to OPF:
source-authority audit, canonical data materialization, deterministic synthetic-label
generation, the classical per-severity model/SHAP shootout, and the
interruption-exact M3 GradientBoosting recommender trainer.  The application server
is not treated as a scheduler and no nested worker pool is introduced.
"""
from __future__ import annotations

import sys
from typing import Iterator

RESTART_EXACT = {
    "exact_resume": True,
    "deterministic": True,
    "idempotent": True,
    "atomic_outputs": True,
}


def _restart_job(
    job_id: str,
    command: list[str],
    *,
    phase: str,
    family: str,
    depends_on: list[str],
    artifacts: list[str],
) -> dict[str, object]:
    return {
        "id": job_id,
        "command": command,
        "phase": phase,
        "family": family,
        "device_capable": False,
        "depends_on": depends_on,
        "is_training_job": False,
        "resume_strategy": "restart_exact",
        "deterministic": True,
        "idempotent": True,
        "atomic_outputs": True,
        "checkpoint_contract": dict(RESTART_EXACT),
        "early_stopping_applicable": False,
        "early_stopping_exception_reason": (
            "deterministic audit/data/estimator transaction without an externally resumable optimizer loop"
        ),
        "completion_artifacts": artifacts,
        "restart_exact_estimator_transaction": phase == "estimator_fit",
    }


def iter_jobs() -> Iterator[dict[str, object]]:
    yield _restart_job(
        "audit-gram-scientific-authority",
        [sys.executable, "scripts/audit_gram_scientific_authority_v1.py"],
        phase="audit",
        family="scientific-authority",
        depends_on=[],
        artifacts=["artifacts/training_control/gram_scientific_authority_v1.json"],
    )
    yield _restart_job(
        "materialize-canonical-data",
        [sys.executable, "backend/generate_canonical_dataset.py"],
        phase="setup",
        family="data/canonical",
        depends_on=["audit-gram-scientific-authority"],
        artifacts=[
            "data/people.csv",
            "data/proposals.csv",
            "data/pairs.csv",
            "data/village_locations.csv",
            "data/village_distances.csv",
        ],
    )
    yield _restart_job(
        "materialize-synthetic-training-labels",
        [sys.executable, "backend/generate_training_labels.py"],
        phase="setup",
        family="data/synthetic-supervision",
        depends_on=["audit-gram-scientific-authority"],
        artifacts=[
            "data/training_labels_high.csv",
            "data/training_labels_normal.csv",
            "data/training_labels_low.csv",
            "data/training_labels.csv",
        ],
    )
    yield _restart_job(
        "fit-nexus-severity-model-zoo",
        [sys.executable, "backend/fit_nexus_weights.py", "--per-severity"],
        phase="estimator_fit",
        family="nexus/model-shootout",
        depends_on=["materialize-synthetic-training-labels"],
        artifacts=["data/fitted_weights_per_severity.json"],
    )
    yield {
        "id": "train-m3-recommender-exact",
        "command": [
            sys.executable,
            "backend/m3_exact_trainer.py",
            "--proposals",
            "data/proposals.csv",
            "--people",
            "data/people.csv",
            "--pairs",
            "data/pairs.csv",
            "--village_locations",
            "data/village_locations.csv",
            "--village_distances",
            "data/village_distances.csv",
            "--out",
            "backend/runtime_data/canonical_model.pkl",
            "--resume_from_checkpoint",
        ],
        "phase": "training",
        "family": "m3/gradient-boosting-recommender",
        "device_capable": True,
        "depends_on": ["materialize-canonical-data"],
        "is_training_job": True,
        "resume_strategy": "exact_checkpoint",
        "checkpoint_contract": {
            "exact_resume": True,
            "optimizer_boundary_equivalent": "gradient_boosting_stage",
            "config_fingerprint": True,
            "patience_state": True,
            "best_model_state": True,
            "sample_order": True,
            "opf_checkpoint_acknowledgement": True,
        },
        "early_stopping": True,
        "early_stopping_applicable": True,
        "early_stopping_metric": "validation_roc_auc",
        "exact_resume_source": "backend/m3_exact_trainer.py:train_exact",
        "early_stopping_source": "backend/m3_exact_trainer.py:train_exact",
        "completion_artifacts": ["backend/runtime_data/canonical_model.pkl"],
        "checkpoint_artifacts": [
            "backend/runtime_data/canonical_model.exact.progress.pkl",
            "backend/runtime_data/canonical_model.exact.best.pkl",
        ],
        "scientific_components": {
            "embedding": "sentence-transformers/all-MiniLM-L6-v2 with TF-IDF fallback",
            "model": "GradientBoostingClassifier",
            "features": [
                "semantic_similarity",
                "similarity_x_willingness",
                "willingness",
                "distance_normalized",
                "distance_decay",
                "availability",
                "severity",
            ],
            "validation": "deterministic holdout ROC-AUC",
        },
    }
