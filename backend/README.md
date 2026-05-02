# Gram Connect Backend

The backend is a FastAPI application that powers problem submission, volunteer coordination, media handling, platform administration, and the Nexus recommendation engine.

## Runtime Model
- Recommendations are produced by `nexus.py` through `recommender_service.py`
- Canonical seed data is loaded from `data/*.csv` into Postgres on startup
- Live runtime state, profile data, problem records, learning events, and platform records are persisted in Postgres
- Uploaded media still lives under `backend/runtime_data/media/` for file serving
- `multimodal_service.py` uses Gemini first and Whisper / CLIP fallbacks when available
- `platform_service.py` powers the platform studio features, audit packs, forms, policy copilot, and export bundles

## Setup
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python generate_canonical_dataset.py
```

## Run
Seeded local demo:
```bash
python start_e2e_backend.py
```

Bare API server:
```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

## Deployment
- Provide a writable Postgres instance and set `DATABASE_URL`
- Install the `vector` extension in that database
- Keep `backend/runtime_data/` writable on the host for uploaded media
- Provide `GEMINI_API_KEY` or `GOOGLE_API_KEY` if you want the Gemini multimodal path
- Use `VITE_API_BASE_URL` in the frontend to point at the deployed backend URL
- The frontend includes an installable PWA shell and role-based dashboards for coordinator, volunteer, supervisor, and partner flows
