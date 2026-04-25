# Repository State

This document records the current implementation status of Gram Connect at the repository level. It is intended to provide a concise and formal reference for maintainers, reviewers, and presentation preparation.

## Current Summary

Gram Connect is a FastAPI and Vite application for community issue intake, volunteer assignment, map-based operations, and persisted recommendation-driven coordination. The repository contains a live backend, a live frontend, a canonical synthetic dataset, a persisted trained recommender bundle, and end-to-end operational flows for villager reporting, coordinator dispatch, and volunteer proof submission.

## Deployment Status

- Public hosted prototype URL: not currently configured in the repository.
- Local demo frontend URL: `http://127.0.0.1:5173`
- Local demo backend API URL: `http://127.0.0.1:8011`
- Local API documentation URL: `http://127.0.0.1:8011/docs`

## Implemented Subsystems

- Backend API service with persisted runtime state and media storage.
- Canonical dataset generator for synthetic proposals, volunteers, pair labels, and operational metadata.
- Persisted recommender bundle with checkpointed training and resumable continuation.
- Multimodal issue intake using image analysis and audio transcription services.
- Coordinator dashboard, volunteer dashboard, villager onboarding, and map-based operational views.
- Persistent media upload and proof submission workflows.
- Formal documentation for the backend interface, model architecture, and demo procedures.

## Intentionally Deferred Subsystems

- Authentication and authorization are deliberately lightweight and remain demo scaffolding.
- CLIP and Whisper are used as pretrained inference components and are not finetuned on repository data.
- Production deployment infrastructure, external secrets management, and hardened access control are out of scope for the current repository state.

## Canonical Artifacts

- Trained recommender bundle: `backend/runtime_data/canonical_model.pkl`
- Best checkpoint: `backend/runtime_data/canonical_model.best.pkl`
- Progress checkpoint: `backend/runtime_data/canonical_model.progress.pkl`
- Runtime state: `backend/runtime_data/app_state.json`
- Uploaded media: `backend/runtime_data/media/`

## Canonical Data Assets

- `data/people.csv`
- `data/proposals.csv`
- `data/pairs.csv`
- `data/village_locations.csv`
- `data/village_distances.csv`
- `data/schedule.csv`
- `data/runtime_profiles.csv`

## Verification Status

The repository includes scripts and test coverage for backend and frontend validation. The documented verification flow covers dataset generation, backend training, backend API verification, frontend type checking, frontend unit tests, frontend build validation, and browser-level integration checks.

## Operational Note

The canonical backend model path is fixed to `backend/runtime_data/canonical_model.pkl`. All runtime code paths are intended to resolve to this artifact unless a training command is explicitly invoked.
