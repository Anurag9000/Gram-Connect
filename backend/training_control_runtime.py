"""Trainer-side bridge for the account-wide OPF pressure controller.

The scheduler owns process/resource policy; Gram-Connect trainers own scientific
state.  A checkpoint acknowledgement is emitted only after a durable checkpoint
exists.  No scheduling decisions live here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Mapping


def checkpoint_requested() -> bool:
    raw = (os.environ.get("TRAINING_CHECKPOINT_REQUEST_FILE") or "").strip()
    return bool(raw) and Path(raw).exists()


def acknowledge_checkpoint(
    *,
    checkpoint: str | Path,
    metadata: Mapping[str, object] | None = None,
) -> None:
    checkpoint_path = Path(checkpoint)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"cannot acknowledge missing checkpoint: {checkpoint_path}")
    request = (os.environ.get("TRAINING_CHECKPOINT_REQUEST_FILE") or "").strip()
    ack = (os.environ.get("TRAINING_CHECKPOINT_ACK_FILE") or "").strip()
    if not request or not Path(request).exists():
        return
    if ack:
        ack_path = Path(ack)
        ack_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": time.time(),
            "checkpoint": checkpoint_path.as_posix(),
            "pid": os.getpid(),
            **dict(metadata or {}),
        }
        temporary = ack_path.with_name(ack_path.name + f".tmp.{os.getpid()}")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, ack_path)
    Path(request).unlink(missing_ok=True)
