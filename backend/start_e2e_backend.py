"""
start_e2e_backend.py — Gram Connect end-to-end backend launcher.

Forge engine requires no trained model. Boot sequence:
  1. Ensure canonical dataset CSVs exist
  2. Reset runtime state (fresh volunteers + problems from CSVs)
  3. Start uvicorn
"""

import uvicorn
from env_loader import load_local_env

load_local_env()

import api_server
from demo_bootstrap import ensure_canonical_dataset


def main() -> None:
    ensure_canonical_dataset()
    api_server.reset_runtime_state()
    uvicorn.run(api_server.app, host="127.0.0.1", port=8011)


if __name__ == "__main__":
    main()
