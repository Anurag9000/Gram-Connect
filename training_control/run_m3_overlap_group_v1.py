#!/usr/bin/env python3
"""Run the exact M3 multi-dataset overlap transaction with strict backend selection."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "training_control"
if str(CONTROL) not in sys.path:
    sys.path.insert(0, str(CONTROL))

from dataset_cohort_runtime_entry import load_runtime  # noqa: E402

SCHEMA = "gram-m3-overlap-group/v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("auto", "cpu", "gpu"), default="auto")
    args = parser.parse_args()

    runtime = load_runtime(ROOT)
    probe = runtime.detect_backend(args.backend)
    env = runtime.subprocess_environment(args.backend)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "backend"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    command = [
        sys.executable,
        "backend/m3_exact_trainer.py",
        "--proposals", "data/proposals.csv",
        "--people", "data/people.csv",
        "--pairs", "data/pairs.csv",
        "--village_locations", "data/village_locations.csv",
        "--village_distances", "data/village_distances.csv",
        "--out", "backend/runtime_data/canonical_model.pkl",
        "--resume_from_checkpoint",
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    certificate = ROOT / "artifacts" / "training_control" / "m3_overlap_group_v1.json"
    certificate.parent.mkdir(parents=True, exist_ok=True)
    temporary = certificate.with_suffix(certificate.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "repository": "Anurag9000/Gram-Connect",
                "datasets": [
                    "data/proposals.csv", "data/people.csv", "data/pairs.csv",
                    "data/village_locations.csv", "data/village_distances.csv",
                ],
                "overlap_group": True,
                "requested_backend": args.backend,
                "selected_backend": probe.selected_device,
                "accelerated_component": "sentence-transformer embeddings when CUDA is selected",
                "cpu_component": "sklearn GradientBoostingClassifier stage-exact warm-start training",
                "exact_resume": True,
                "early_stopping": True,
                "model_training_executed": True,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, certificate)
    print(json.dumps({"status": "complete", "backend": probe.selected_device}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
