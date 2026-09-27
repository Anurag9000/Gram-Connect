"""Gram-Connect live dataset cohort uses immutable v3; v2 remains intact."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "training_control" / "dataset_cohort_runtime_entry.py"
NEW = ROOT / "training_control" / "dataset_cohort_runtime_entry_v3.py"


def test_canonical_v3_pin_without_mutating_v2():
    data = OLD.read_bytes()
    assert hashlib.sha1(f"blob {len(data)}\\0".encode("ascii") + data).hexdigest() == "62312e09bfcbc724cf56eaa4bd235969ad8851aa"
    source = NEW.read_text(encoding="utf-8")
    ast.parse(source)
    for marker in (
        "955a092e4a3e2cc04adfd8007206acd6d1341dce",
        "8afef6ade42b9885878102d42e26ec3ab2a18bf3",
        "0160deb303f6a4d2a48b8453244dc01ceaae1295",
        "e6455266b63bed08691cfa76e620060f99eca35a",
        "training/dataset_cohort_runtime_v3.py",
    ):
        assert marker in source
    for name in ("run_nexus_severity_group_v1.py", "run_m3_overlap_group_v1.py"):
        worker = ROOT / "training_control" / name
        assert "from dataset_cohort_runtime_entry_v3 import load_runtime" in worker.read_text(encoding="utf-8")
