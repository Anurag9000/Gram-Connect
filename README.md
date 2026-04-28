# Gram Connect

Gram Connect is a full-stack community operations app with a FastAPI backend and a Vite + React frontend. The current runtime uses the Nexus scoring engine for recommendations, with optional multimodal fallbacks for transcription and image analysis.

## Repo Layout
- `backend/`: FastAPI service, Nexus recommender, multimodal helpers, tests, and runtime scripts
- `frontend/`: Vite + React + TypeScript UI
- `data/`: canonical CSV datasets and test fixtures
- `docs/`: architecture, model, and repository-state notes

## Current Runtime
- Recommendation requests are served by `backend/nexus.py` through `backend/recommender_service.py`
- Runtime state is seeded from `data/*.csv` and stored under `backend/runtime_data/`
- The backend can boot without a trained model; legacy training utilities remain only for verification and experimentation

## Local Development

### Backend
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python generate_canonical_dataset.py
python start_e2e_backend.py
```

If you want the bare API server instead of the seeded demo launcher:
```bash
python -m uvicorn api_server:app --host 127.0.0.1 --port 8011
```

### Frontend
```bash
cd frontend
npm install
$env:VITE_API_BASE_URL="http://127.0.0.1:8011"
npm run dev
```

Production preview:
```bash
npm run build
npm run preview -- --host 0.0.0.0 --port 4173
```

## Deployment

### Frontend on Vercel
- Set the build command to `npm run build`
- Set the output directory to `dist`
- Set `VITE_API_BASE_URL` to your deployed backend URL
- Deploy from the `frontend/` folder, or configure the repo root so Vercel uses `frontend/package.json`

### Backend on a Python Host
Use any platform that runs a persistent FastAPI app, such as Render, Railway, Fly.io, or a VM.

Start command:
```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port $PORT
```

If the platform does not provide `$PORT`, use `8000` or another open port.

### Deployment Notes
- The frontend and backend are deployed separately
- The frontend must point at the backend with `VITE_API_BASE_URL`
- The backend serves API traffic only; it does not need the frontend build artifacts

## Verification
```bash
cd backend
python -m pytest tests -q

cd ..\frontend
npm run typecheck
npm run lint
npm run build
```

For the full repo check, use:
```bash
bash scripts/full_verify.sh
```
Run that from Git Bash, WSL, or another Bash shell.

## Demo Credentials
- Coordinator: `coordinator@test.com` / `password`
- Volunteer: `volunteer@test.com` / `password`

## References
- `backend/README.md`: backend-specific runtime notes
- `backend/HOW_TO_RUN.md`: backend operational guide
- `docs/repository_state.md`: current implementation scope
- `docs/model_spec.md`: Nexus scoring details
