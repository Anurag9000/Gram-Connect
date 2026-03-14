# SocialCode

SocialCode is a FastAPI + Vite application for matching community problems to volunteer teams. The repo currently runs in a Linux workflow and has been verified with backend tests, frontend tests, typecheck, lint, build, and a live recommendation smoke run.

## Repo Layout
- `backend/`: FastAPI service, recommender logic, multimodal helpers, tests
- `frontend/`: Vite + React + TypeScript UI
- `data/`: dataset assets used when present
- `docs/`: backend contract notes

## Verified Linux Setup

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest tests -q
python -m uvicorn api_server:app --host 127.0.0.1 --port 8011
```

Notes:
- PyTorch is intentionally installed from the official CUDA wheel index first.
- If `backend/model.pkl` is missing, `/recommend` still works using the runtime TF-IDF fallback.
- Dataset paths auto-resolve from the repo or from `GRAM_CONNECT_*` environment variables.

### Frontend
In a second terminal:
```bash
cd frontend
npm install
printf 'VITE_API_BASE_URL=http://127.0.0.1:8011\n' > .env
npm test -- --run
npm run typecheck
npm run lint
npm run build
npm run dev
```

Open the URL printed by Vite, usually `http://127.0.0.1:5173`.

## Test Credentials
- Coordinator: `coordinator@test.com` / `password`
- Volunteer: `volunteer@test.com` / `password`

## What Was Verified
- Backend test suite: passing
- Frontend unit tests: passing
- Frontend typecheck: passing
- Frontend lint: passing
- Frontend production build: passing
- Backend live smoke checks:
  - `GET /health`
  - `POST /recommend`

## Path Overrides
Optional backend overrides:
```bash
export GRAM_CONNECT_MODEL_PATH=/absolute/path/to/model.pkl
export GRAM_CONNECT_PEOPLE_CSV=/absolute/path/to/people.csv
export GRAM_CONNECT_PROPOSALS_CSV=/absolute/path/to/proposals.csv
export GRAM_CONNECT_PAIRS_CSV=/absolute/path/to/pairs.csv
export GRAM_CONNECT_VILLAGE_LOCATIONS_CSV=/absolute/path/to/village_locations.csv
export GRAM_CONNECT_DISTANCE_CSV=/absolute/path/to/village_distances.csv
```
