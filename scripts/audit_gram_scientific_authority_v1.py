#!/usr/bin/env python3
"""Fail-closed source/catalog audit for Gram-Connect's retained ML surface."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "training_control"
if str(CONTROL) not in sys.path:
    sys.path.insert(0, str(CONTROL))

import gram_scientific_job_catalog_v1 as catalog  # noqa: E402

OUTPUT = ROOT / "artifacts" / "training_control" / "gram_scientific_authority_v1.json"

# These retained source files are the only current scientific fit surfaces.  The
# legacy M3 trainer is scientifically represented by the exact central replacement.
COVERED_FIT_SOURCES = {
    "backend/m3_trainer.py": "train-m3-recommender-exact",
    "backend/m3_exact_trainer.py": "train-m3-recommender-exact",
    "backend/fit_nexus_weights.py": "fit-nexus-severity-model-zoo",
}
FIT_CALLS = {"fit", "partial_fit", "fit_generator", "train_on_batch", "backward"}
FIT_CONSTRUCTORS = {
    "GradientBoostingClassifier",
    "LogisticRegression",
    "RandomForestClassifier",
    "XGBClassifier",
    "LGBMClassifier",
}


def _scientific_calls(path: Path) -> list[dict[str, object]]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    findings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in FIT_CALLS:
                findings.append({"line": int(node.lineno), "kind": "fit_call", "symbol": node.func.attr})
            elif isinstance(node.func, ast.Name) and node.func.id in FIT_CONSTRUCTORS:
                findings.append({"line": int(node.lineno), "kind": "model_constructor", "symbol": node.func.id})
    return findings


def _source_tokens(relative: str, tokens: tuple[str, ...], unresolved: list[dict[str, object]]) -> None:
    path = ROOT / relative
    if not path.is_file():
        unresolved.append({"type": "missing_source_evidence", "path": relative})
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [token for token in tokens if token not in text]
    if missing:
        unresolved.append({"type": "missing_source_tokens", "path": relative, "tokens": missing})


def _atomic_json(payload: dict[str, object]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)


def main() -> int:
    jobs = [dict(job) for job in catalog.iter_jobs()]
    job_ids = {str(job.get("id")) for job in jobs}
    unresolved: list[dict[str, object]] = []
    if len(job_ids) != len(jobs):
        unresolved.append({"type": "duplicate_or_missing_catalog_job_ids"})

    observed_fit_sources: dict[str, list[dict[str, object]]] = {}
    parse_errors: list[dict[str, object]] = []
    for path in sorted((ROOT / "backend").glob("*.py")):
        try:
            findings = _scientific_calls(path)
        except SyntaxError as exc:
            parse_errors.append(
                {"path": path.relative_to(ROOT).as_posix(), "line": int(exc.lineno or 0), "message": str(exc)}
            )
            continue
        if findings:
            observed_fit_sources[path.relative_to(ROOT).as_posix()] = findings
    if parse_errors:
        unresolved.append({"type": "python_parse_errors", "values": parse_errors})

    uncovered = sorted(set(observed_fit_sources) - set(COVERED_FIT_SOURCES))
    if uncovered:
        unresolved.append(
            {
                "type": "retained_fit_sources_without_central_binding",
                "values": {name: observed_fit_sources[name] for name in uncovered},
            }
        )
    stale_bindings = {
        path: job_id
        for path, job_id in COVERED_FIT_SOURCES.items()
        if path not in observed_fit_sources or job_id not in job_ids
    }
    if stale_bindings:
        unresolved.append({"type": "stale_source_to_job_bindings", "values": stale_bindings})

    _source_tokens(
        "backend/m3_exact_trainer.py",
        (
            "config_fingerprint",
            "best_model",
            "no_improve",
            "permutation",
            "checkpoint_requested",
            "acknowledge_checkpoint",
            "validation_roc_auc",
        ),
        unresolved,
    )
    _source_tokens(
        "backend/training_control_runtime.py",
        ("TRAINING_CHECKPOINT_REQUEST_FILE", "TRAINING_CHECKPOINT_ACK_FILE", "acknowledge_checkpoint"),
        unresolved,
    )
    _source_tokens(
        "backend/m3_trainer.py",
        ("GradientBoostingClassifier", "warm_start=True", "n_iter_no_change", "resume_from_checkpoint"),
        unresolved,
    )
    _source_tokens(
        "backend/fit_nexus_weights.py",
        ("LogisticRegression", "RandomForestClassifier", "XGBClassifier", "LGBMClassifier", "StratifiedKFold", "random_state=42"),
        unresolved,
    )
    _source_tokens(
        "backend/generate_training_labels.py",
        ("random.seed(2024)", "training_labels_high.csv", "training_labels_normal.csv", "training_labels_low.csv"),
        unresolved,
    )
    _source_tokens(
        "backend/generate_canonical_dataset.py",
        ("build_pairs", "people.csv", "proposals.csv", "pairs.csv", "village_distances.csv"),
        unresolved,
    )

    dependencies = {str(job["id"]): set(str(value) for value in (job.get("depends_on") or [])) for job in jobs}
    expected_edges = {
        "materialize-canonical-data": {"audit-gram-scientific-authority"},
        "materialize-synthetic-training-labels": {"audit-gram-scientific-authority"},
        "fit-nexus-severity-model-zoo": {"materialize-synthetic-training-labels"},
        "train-m3-recommender-exact": {"materialize-canonical-data"},
    }
    for job_id, expected in expected_edges.items():
        if dependencies.get(job_id) != expected:
            unresolved.append(
                {"type": "dag_dependency_mismatch", "job": job_id, "expected": sorted(expected), "actual": sorted(dependencies.get(job_id, set()))}
            )

    payload = {
        "schema_version": 1,
        "repository": "Anurag9000/Gram-Connect",
        "status": "PASS" if not unresolved else "FAIL",
        "catalog_job_ids": sorted(job_ids),
        "retained_fit_sources": observed_fit_sources,
        "covered_fit_sources": COVERED_FIT_SOURCES,
        "unresolved": unresolved,
        "complete": not unresolved,
        "source_configuration_only": True,
        "training_executed_by_audit": False,
        "benchmark_claim_emitted": False,
    }
    _atomic_json(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not unresolved else 2


if __name__ == "__main__":
    raise SystemExit(main())
