# Demo Checklist

## Model And Data
- Confirm `backend/runtime_data/canonical_model.pkl` exists.
- Confirm checkpoint artifacts exist:
  - `backend/runtime_data/canonical_model.best.pkl`
  - `backend/runtime_data/canonical_model.progress.pkl`
- Confirm canonical mock data exists in `data/`:
  - `people.csv`
  - `proposals.csv`
  - `pairs.csv`
  - `village_locations.csv`
  - `village_distances.csv`
  - `schedule.csv`
  - `runtime_profiles.csv`

## Backend Startup
- Enter the backend virtual environment:
  - `source backend/.verify-venv/bin/activate`
- Start the backend demo server:
  - `python backend/start_e2e_backend.py`
- Confirm the API is live:
  - `GET http://127.0.0.1:8011/health`

## Frontend Startup
- Install frontend dependencies if needed:
  - `cd frontend && npm install`
- Point the frontend at the demo backend:
  - `printf 'VITE_API_BASE_URL=http://127.0.0.1:8011\n' > frontend/.env`
- Start the UI:
  - `npm run dev`

## Demo Flow
- Open `/villager-onboarding` and save a villager profile.
- Open `/submit` and submit a problem with:
  - title
  - description
  - category
  - village
  - image upload
  - optional audio upload
- Open `/dashboard` and generate recommendations.
- Open `/map` and verify problem markers load.
- Open `/volunteer-dashboard` and complete a task with before/after proof.
- Return to `/dashboard` and confirm problem/proof state updated.

## Verification
- Backend verification:
  - `backend/.verify-venv/bin/python backend/run_full_verification.py`
- Frontend checks:
  - `npm --prefix frontend run typecheck`
  - `npm --prefix frontend run build`
  - `npx vitest run`

## What To Say In The Pitch
- The recommender bundle is persisted.
- The frontend uses the live backend, not mock-only flows.
- Problem submission, map, assignments, and proof uploads are all wired end to end.
- The demo runtime can be regenerated from the canonical dataset and retrained deterministically.
