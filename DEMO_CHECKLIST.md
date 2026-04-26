# Gram Connect Demo Procedure

## Engine and Data

- Confirm the Nexus engine is configured properly in `backend/nexus.py` (no `.pkl` models required).
- Confirm canonical mock data exists in `data/`:
  - `people.csv`
  - `proposals.csv`
  - `pairs.csv`
  - `village_locations.csv`
  - `village_distances.csv`
  - `schedule.csv`
  - `runtime_profiles.csv`

## Backend Startup

1. Enter the backend virtual environment:
   - `source backend/.verify-venv/bin/activate`
2. Start the backend demo server:
   - `python backend/start_e2e_backend.py`
3. Confirm that the API is live:
   - `GET http://127.0.0.1:8011/health`

## Frontend Startup

1. Install frontend dependencies if required:
   - `cd frontend && npm install`
2. Point the frontend at the demo backend:
   - `printf 'VITE_API_BASE_URL=http://127.0.0.1:8011\n' > frontend/.env`
3. Start the user interface:
   - `npm run dev`

## Demonstration Sequence

- Open `/villager-onboarding` and save a villager profile.
- Open `/submit` and submit a problem with:
  - title
  - description
  - category
  - village
  - image upload
  - optional audio upload
- Open `/dashboard` and generate recommendations.
- Open `/map` and verify that problem markers load.
- Open `/volunteer-dashboard` and complete a task with before-and-after proof.
- Return to `/dashboard` and confirm that problem and proof state have updated.

## Verification

- Backend verification:
  - `backend/.verify-venv/bin/python backend/run_full_verification.py`
- Frontend verification:
  - `npm --prefix frontend run typecheck`
  - `npm --prefix frontend run build`
  - `npx vitest run`

## Presentation Summary

- The engine runs instantaneously on mathematically derived SHAP weights (Zero ML model persistence required).
- The frontend uses the live backend rather than mock-only flows.
- Problem submission, map rendering, assignment generation, and proof uploads are integrated end to end.
- The demo runtime dynamically bootstraps from the canonical CSVs on startup without needing training.
- The platform is fully internationalized to 12 regional Indian languages using i18n for broad accessibility.
- Automatic severity triage uses Google Gemini multimodal inference for context-aware problem routing.
