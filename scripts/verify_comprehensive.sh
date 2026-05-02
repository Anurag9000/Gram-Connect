#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

backend/.venv/bin/pytest backend/test_comprehensive_suite.py -q
(cd frontend && npm run typecheck)
(cd frontend && npm test -- src/tests/comprehensive_feature_coverage.test.tsx)
