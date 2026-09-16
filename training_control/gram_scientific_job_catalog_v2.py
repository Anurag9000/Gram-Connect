#!/usr/bin/env python3
"""Physical dataset-group scientific DAG for Gram-Connect v2.

The v1 catalog remains the logical retained-training authority.  v2 changes only
execution topology:

* Nexus HIGH, LOW and NORMAL severity datasets are three single-dataset groups.
  Each group loads/transforms its CSV once and evaluates the same four retained
  estimator families against the shared X/y matrix.
* the three groups are ordered deterministically after the primary descending
  model-family-count rule (all contain four families);
* their outputs are merged back to the legacy fitted_weights_per_severity.json;
* M3 consumes five data sources and is therefore the final overlap group;
* all classical estimators remain whole-fit/stage transactions instead of falsely
  claiming minibatch synchronization.
"""
from __future__ import annotations

import sys
from typing import Any, Iterator

SCHEMA = "gram-physical-dataset-catalog/v2"
RESTART_EXACT = {
    "exact_resume": True,
    "deterministic": True,
    "idempotent": True,
    "atomic_outputs": True,
}


def _job(
    job_id: str,
    command: list[str],
    *,
    phase: str,
    family: str,
    depends_on: list[str],
    artifacts: list[str],
    device_capable: bool = False,
    training: bool = False,
    early: bool = False,
    dataset_group_index: int | None = None,
    dataset_parent: str | None = None,
    overlap: bool = False,
    model_family_count: int = 0,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": job_id,
        "command": command,
        "phase": phase,
        "family": family,
        "device_capable": device_capable,
        "cpu_capable": True,
        "gpu_capable": bool(device_capable),
        "depends_on": depends_on,
        "is_training_job": training,
        "resume_strategy": "exact_checkpoint" if early else "restart_exact",
        "checkpoint_contract": dict(RESTART_EXACT),
        "deterministic": True,
        "idempotent": True,
        "atomic_outputs": True,
        "early_stopping_applicable": early,
        "completion_artifacts": artifacts,
        "dataset_cohort_schema": SCHEMA,
    }
    if not early:
        row["early_stopping_exception_reason"] = (
            "classical whole-estimator/audit/setup transaction has no valid shared minibatch early-stopping boundary"
        )
    else:
        row["early_stopping"] = True
        row["early_stopping_metric"] = "validation_roc_auc"
        row["checkpoint_contract"].update(
            {
                "optimizer_boundary_equivalent": "gradient_boosting_stage",
                "config_fingerprint": True,
                "patience_state": True,
                "best_model_state": True,
                "sample_order": True,
                "opf_checkpoint_acknowledgement": True,
            }
        )
    if dataset_group_index is not None:
        row.update(
            {
                "dataset_group_index": int(dataset_group_index),
                "dataset_parent": str(dataset_parent),
                "overlap": bool(overlap),
                "model_family_count": int(model_family_count),
                "group_order_rule": "descending_distinct_model_families_then_dataset_key_overlap_last",
            }
        )
    return row


def iter_jobs() -> Iterator[dict[str, Any]]:
    yield _job(
        "audit-gram-scientific-authority",
        [sys.executable, "scripts/audit_gram_scientific_authority_v1.py"],
        phase="audit",
        family="scientific-authority",
        depends_on=[],
        artifacts=["artifacts/training_control/gram_scientific_authority_v1.json"],
    )
    yield _job(
        "materialize-canonical-data",
        [sys.executable, "backend/generate_canonical_dataset.py"],
        phase="setup",
        family="data/canonical",
        depends_on=["audit-gram-scientific-authority"],
        artifacts=[
            "data/people.csv", "data/proposals.csv", "data/pairs.csv",
            "data/village_locations.csv", "data/village_distances.csv",
        ],
    )
    yield _job(
        "materialize-synthetic-training-labels",
        [sys.executable, "backend/generate_training_labels.py"],
        phase="setup",
        family="data/synthetic-supervision",
        depends_on=["audit-gram-scientific-authority"],
        artifacts=[
            "data/training_labels_high.csv", "data/training_labels_normal.csv",
            "data/training_labels_low.csv", "data/training_labels.csv",
        ],
    )

    # All three single-dataset groups have the same four distinct families, so the
    # deterministic dataset-key tie-break is HIGH -> LOW -> NORMAL.
    severity_groups = (
        (1, "high", "data/training_labels_high.csv"),
        (2, "low", "data/training_labels_low.csv"),
        (3, "normal", "data/training_labels_normal.csv"),
    )
    previous: list[str] = ["materialize-synthetic-training-labels"]
    severity_ids: list[str] = []
    for index, severity, dataset in severity_groups:
        job_id = f"fit-nexus-{severity}-dataset-group"
        artifact = f"artifacts/training_control/nexus_{severity}_group_v1.json"
        yield _job(
            job_id,
            [
                sys.executable,
                "training_control/run_nexus_severity_group_v1.py",
                "--severity", severity,
                "--backend", "auto",
                "--output", artifact,
            ],
            phase="estimator_fit",
            family="nexus/model-shootout",
            depends_on=list(previous),
            artifacts=[artifact],
            device_capable=True,
            training=True,
            dataset_group_index=index,
            dataset_parent=dataset,
            overlap=False,
            model_family_count=4,
        )
        previous = [job_id]
        severity_ids.append(job_id)

    yield _job(
        "merge-nexus-severity-groups",
        [sys.executable, "training_control/merge_nexus_severity_groups_v1.py"],
        phase="aggregation",
        family="nexus/model-shootout",
        depends_on=list(severity_ids),
        artifacts=[
            "data/fitted_weights_per_severity.json",
            "artifacts/training_control/nexus_severity_merge_v1.json",
        ],
    )

    yield _job(
        "train-m3-recommender-overlap-group",
        [sys.executable, "training_control/run_m3_overlap_group_v1.py", "--backend", "auto"],
        phase="training",
        family="m3/gradient-boosting-recommender",
        depends_on=["materialize-canonical-data", "merge-nexus-severity-groups"],
        artifacts=[
            "backend/runtime_data/canonical_model.pkl",
            "artifacts/training_control/m3_overlap_group_v1.json",
        ],
        device_capable=True,
        training=True,
        early=True,
        dataset_group_index=4,
        dataset_parent="__overlap__",
        overlap=True,
        model_family_count=1,
    )


def catalog_metadata() -> dict[str, Any]:
    rows = list(iter_jobs())
    groups = [row for row in rows if row.get("dataset_group_index") is not None]
    ordered = sorted(groups, key=lambda row: int(row["dataset_group_index"]))
    families = [int(row["model_family_count"]) for row in ordered if not row["overlap"]]
    return {
        "schema": SCHEMA,
        "logical_authority": "training_control/gram_scientific_job_catalog_v1.py",
        "physical_authority": "training_control/gram_scientific_job_catalog_v2.py",
        "dataset_groups": len(groups),
        "single_dataset_groups": len([row for row in groups if not row["overlap"]]),
        "overlap_groups": len([row for row in groups if row["overlap"]]),
        "overlap_group_last": bool(ordered and ordered[-1]["overlap"]),
        "single_group_family_counts_nonincreasing": families == sorted(families, reverse=True),
        "cpu_variant_required": True,
        "gpu_first_variant_required": True,
        "auto_backend": "gpu_if_available_else_cpu",
        "classical_shared_batch_claim": False,
        "classical_shared_dataset_materialization": True,
        "execution_claim_emitted": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(catalog_metadata(), indent=2, sort_keys=True))
