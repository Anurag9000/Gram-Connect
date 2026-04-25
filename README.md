# Gram Connect

Gram Connect is a FastAPI and Vite application for reporting community issues, coordinating volunteer response, and visualising operational status through a live browser interface.

## Repo Layout
- `backend/`: FastAPI service, recommender logic, multimodal helpers, and tests
- `frontend/`: Vite, React, and TypeScript user interface
- `data/`: canonical seeded dataset assets and media fixtures
- `docs/`: formal repository documentation and architecture references

## System Architecture

![Gram Connect Architecture](docs/architecture_diagram.png)

The system uses a decoupled architecture with a FastAPI backend and a Vite-based frontend. It integrates multimodal inference services for image analysis and audio transcription together with a persisted recommender bundle for volunteer assignment.

## Model Spec

The persisted recommender architecture, feature stack, early-stopping policy, and runtime behaviour are documented in [docs/model_spec.md](docs/model_spec.md).

## Repository State

The current implementation status, canonical artifacts, intentionally deferred subsystems, and verification scope are documented in [docs/repository_state.md](docs/repository_state.md).

## Canonical Seeded Data
- `backend/generate_canonical_dataset.py` is the source of truth for the synthetic dataset.
- Running it regenerates:
  - `data/people.csv`
  - `data/proposals.csv`
  - `data/pairs.csv`
  - `data/village_locations.csv`
  - `data/village_distances.csv`
  - `data/schedule.csv`
  - `data/runtime_profiles.csv`
- The backend seeds its runtime state from those files and persists live application state under `backend/runtime_data/app_state.json`.
- The trained demo model is persisted at `backend/runtime_data/canonical_model.pkl` and is the canonical runtime model path.

## Environment and Verification

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
python -m pip install pytest
python generate_canonical_dataset.py
python -m pytest tests -q
python run_full_verification.py
python -m uvicorn api_server:app --host 127.0.0.1 --port 8011
```

Notes:
- PyTorch is installed from the official CUDA wheel index before the repository requirements.
- `run_full_verification.py` trains and persists `backend/runtime_data/canonical_model.pkl`, then verifies recommendation inference, schedule filtering, image analysis, and audio transcription.
- The backend runtime fails closed if the trained bundle is missing. In normal demo flow, `backend/start_e2e_backend.py` or the FastAPI startup bootstrap trains it before serving.
- Dataset paths resolve from the repository defaults or from `GRAM_CONNECT_*` environment variables.
- The backend runtime state is seeded from the canonical CSV files rather than handwritten demo records.

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
npm run test:e2e
npm run dev
```

Open the URL printed by Vite, usually `http://127.0.0.1:5173`.

### Primary Demo Routes
- `/` home and entry points
- `/villager-onboarding` villager profile setup
- `/submit` problem submission with audio and image persistence
- `/dashboard` coordinator dashboard with AI assignment and embedded map
- `/map` full-screen geospatial view
- `/volunteer-dashboard` volunteer tasks and proof upload flow
- `/profile` volunteer profile editor

## Demo Access Credentials
- Coordinator: `coordinator@test.com` / `password`
- Volunteer: `volunteer@test.com` / `password`

## Verification Scope
- Backend test suite
- Frontend unit tests
- Frontend type checking
- Frontend linting
- Frontend production build
- Backend full model verification:
  - real model training
  - recommendation inference
  - schedule-filter behavior
  - `POST /recommend`
  - `POST /analyze-image`
  - `POST /transcribe`
- Frontend Playwright integration:
  - coordinator login and dashboard filtering
  - AI team generation and assignment
  - image-assisted problem submission
  - volunteer task completion flow

## One-Command Verification
```bash
scripts/full_verify.sh
```

That runs:
- backend dataset generation
- backend unit and smoke tests
- backend full model verification
- frontend unit tests
- frontend typecheck
- frontend lint
- frontend production build
- frontend browser integration tests

## Path Overrides
The canonical trained model is served from `backend/runtime_data/canonical_model.pkl`.
Optional dataset overrides remain available for regeneration and controlled experiments:
`GRAM_CONNECT_PEOPLE_CSV`, `GRAM_CONNECT_PROPOSALS_CSV`, `GRAM_CONNECT_PAIRS_CSV`, `GRAM_CONNECT_VILLAGE_LOCATIONS_CSV`, and `GRAM_CONNECT_DISTANCE_CSV`.
