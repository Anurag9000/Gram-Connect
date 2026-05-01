# Backend Operational Guide

## Purpose

This document covers the current Gram Connect backend runtime. The live recommendation path uses the Nexus engine and does not require model training. State and learning history are stored in Postgres.

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python generate_canonical_dataset.py
```

## Run

Seeded demo launcher:

```bash
python start_e2e_backend.py
```

Bare API server:

```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

## Notes

- `backend/runtime_data/` is created automatically and holds uploaded media only.
- Postgres is the source of truth for canonical seed data, live runtime state, and learning events.
- Set `DATABASE_URL` to point at a writable Postgres instance with the `vector` extension enabled.
- `GRAM_CONNECT_SKIP_BOOTSTRAP=1` disables startup seeding when you want a manual boot.
- The backend expects `data/*.csv` to be present, or alternative paths via `GRAM_CONNECT_*` environment variables.
