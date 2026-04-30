# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the FastAPI service, recommender logic, multimodal helpers, and backend tests in `backend/tests/`. `frontend/` contains the Vite + React + TypeScript app, with UI code in `frontend/src/`, unit tests beside components/pages as `*.test.tsx`, and Playwright e2e tests in `frontend/tests/e2e/`. Shared documentation lives in `docs/`, and seeded dataset assets live in `data/`.

## Build, Test, and Development Commands
- `cd backend && .venv/bin/python generate_canonical_dataset.py`: regenerate canonical CSV fixtures.
- `cd backend && .venv/bin/python -m pytest -q tests test_suite.py`: run backend tests.
- `cd backend && .venv/bin/python run_full_verification.py`: run the backend verification flow.
- `cd frontend && npm run dev`: start the frontend dev server.
- `cd frontend && npm test -- --run`: run frontend unit tests.
- `cd frontend && npm run typecheck`: run TypeScript checks.
- `cd frontend && npm run lint`: run ESLint.
- `cd frontend && npm run build`: produce a production build.
- `cd frontend && npm run test:e2e`: run Playwright tests.
- `scripts/full_verify.sh`: run the repository-wide verification sequence.

## Coding Style & Naming Conventions
Follow the existing style in each stack. Python code uses 4-space indentation and clear, explicit function names. Frontend code follows ESLint + TypeScript conventions, uses 2-space indentation, and keeps React components in `PascalCase` files such as `CoordinatorDashboard.tsx`. Use `snake_case` for Python modules and test files like `test_nexus_utils.py`, and `*.test.tsx` or `*.spec.ts` for frontend tests.

## Testing Guidelines
Add backend tests under `backend/tests/` with `test_*.py` names. Add frontend unit tests next to the component or page they cover, and add browser flows under `frontend/tests/e2e/`. Prefer focused tests for API behavior, translation coverage, and critical UI paths. Run the smallest relevant test set first, then finish with `scripts/full_verify.sh` before large changes.

## Commit & Pull Request Guidelines
Use conventional, lowercase commits such as `feat:`, `fix:`, `refactor:`, or `docs:`; scoped forms like `feat(forge):` also appear in history. Keep PRs focused, describe the user-facing change, list verification commands run, and include screenshots or screen recordings for UI updates. Link related issues when available.

## Security & Configuration Tips
Do not commit local secrets or environment files such as `backend/.env.local` or `frontend/.env.local`. Generated runtime artifacts under `backend/runtime_data/` are ignored and should be recreated locally rather than checked in.
