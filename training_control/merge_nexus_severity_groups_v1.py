#!/usr/bin/env python3
"""Merge the three physical Nexus severity-group certificates into legacy output."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "gram-nexus-severity-merge/v1"
SEVERITIES = ((0, "low"), (1, "normal"), (2, "high"))


def _atomic_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    merged = {}
    source_certificates = []
    for severity_id, name in SEVERITIES:
        path = ROOT / "artifacts" / "training_control" / f"nexus_{name}_group_v1.json"
        if not path.is_file():
            raise SystemExit(f"missing Nexus severity group certificate: {path}")
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("schema") != "gram-nexus-severity-group/v1":
            raise RuntimeError(f"Nexus severity certificate schema drift: {path}")
        if int(row.get("severity_id", -1)) != severity_id or row.get("severity") != name:
            raise RuntimeError(f"Nexus severity certificate identity drift: {path}")
        result = row.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"Nexus severity group lacks result mapping: {path}")
        merged[str(severity_id)] = result
        source_certificates.append(path.relative_to(ROOT).as_posix())

    legacy = ROOT / "data" / "fitted_weights_per_severity.json"
    _atomic_json(legacy, merged)
    certificate = ROOT / "artifacts" / "training_control" / "nexus_severity_merge_v1.json"
    _atomic_json(
        certificate,
        {
            "schema": SCHEMA,
            "repository": "Anurag9000/Gram-Connect",
            "source_certificates": source_certificates,
            "legacy_output": legacy.relative_to(ROOT).as_posix(),
            "severity_groups": [name for _, name in SEVERITIES],
            "model_training_executed": False,
        },
    )
    print(json.dumps({"status": "complete", "output": str(legacy)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
