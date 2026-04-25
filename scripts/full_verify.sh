#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT/backend"
.venv/bin/python generate_canonical_dataset.py
.venv/bin/python -m pytest -q tests test_suite.py
.venv/bin/python run_full_verification.py

cd "$REPO_ROOT/frontend"
npm test -- --run
npm run typecheck
npm run lint
npm run build
npm run test:e2e
