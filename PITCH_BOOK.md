# Gram Connect Investor Brief

## Executive Summary

Gram Connect is a community issue reporting and volunteer assignment platform with a persisted recommender model, multimodal issue intake, map-based operations, and proof-backed task completion.

## Product Scope

- Villagers may submit problems with text, image, and optional audio.
- The backend analyses submitted media, persists the report, and stores media artefacts.
- Coordinators may generate volunteer teams from the trained recommender bundle.
- Volunteers may inspect assignments, upload before-and-after proof, and complete work.
- The coordinator dashboard and map view reflect the live backend state.

## Model Scope

- Only the recommender bundle is trained on repository data.
- The live canonical bundle is stored at `backend/runtime_data/canonical_model.pkl`.
- The bundle is built from the canonical synthetic dataset in `data/`.
- CLIP and Whisper are used as pretrained inference services only.

## Training Record

- Verified canonical training ran on `2026-04-22` in the `Asia/Kolkata` timezone.
- The training began at approximately `22:13:11 IST`.
- The verified run completed at approximately `22:20:12 IST`.
- A later continuation run resumed from the best checkpoint and was terminated by the configured patience rule after additional boosting stages.

## Training Configuration

- Entry point: `backend/run_full_verification.py`
- Trainer: `backend/m3_trainer.py`
- Model family: `GradientBoostingClassifier`
- Text backend: `tfidf` fallback in the verified run
- Training recipe:
  - `n_estimators=600`
  - `learning_rate=0.03`
  - `subsample=0.85`
  - `max_depth=3`
  - `validation_fraction=0.2`
  - `n_iter_no_change=20`
  - `tol=1e-4`
- The trainer operates stage by stage with `warm_start=True`.
- After each boosting stage it writes a progress checkpoint.
- Whenever validation improves, it writes a best checkpoint.
- If a run is interrupted, the next run resumes from the best saved checkpoint by default.

## Hold-Out Metrics

- The latest evaluation uses a deterministic `70/15/15` train-validation-test split.
- Training metrics are tracked on the validation split during boosting, and final reporting is performed on the held-out test split.
- Validation metrics on the latest persisted canonical bundle:
  - Accuracy: `0.8814`
  - ROC AUC: `0.9479`
  - Log loss: `0.2949`
- Test metrics on the latest persisted canonical bundle:
  - Accuracy: `0.8611`
  - ROC AUC: `0.9385`
  - Log loss: `0.3135`
- The lowest validation loss observed during the latest continuation run was `0.2949`.

## Early Stopping Behaviour

- The trainer uses manual early stopping logic rather than a single opaque fit call.
- Validation is evaluated after each boosting stage.
- If validation does not improve for `n_iter_no_change` consecutive stages, the run stops early.
- In the verified training run, validation continued to improve sufficiently that the run reached the configured stage ceiling.
- In the continuation run, the trainer resumed from the best checkpoint, continued training until the patience condition was met, and then stopped.
- Early stopping is therefore active, checkpointed, and resumable.

## Persisted Artifacts

- `backend/runtime_data/canonical_model.pkl`
- `backend/runtime_data/canonical_model.best.pkl`
- `backend/runtime_data/canonical_model.progress.pkl`
- `backend/runtime_data/app_state.json`
- `backend/runtime_data/media/`

## Data Coverage

- Training data exists for the recommender bundle:
  - `data/people.csv`
  - `data/proposals.csv`
  - `data/pairs.csv`
  - `data/village_locations.csv`
  - `data/village_distances.csv`
  - `data/schedule.csv`
  - `data/runtime_profiles.csv`
- There is no finetuning corpus for Whisper or CLIP in the repository; they remain frozen pretrained services.

## Demonstration Sequence

1. Start the backend demo server.
2. Open the frontend.
3. Submit a problem with media.
4. Open the dashboard and generate recommendations.
5. Open the map and inspect live case locations.
6. Open the volunteer dashboard and submit proof.
7. Confirm that backend state updates across all views.

## Verification Status

- Backend unit tests: passed
- Frontend type checking: passed
- Frontend unit tests: passed
- Frontend production build: passed
- Full backend verification: passed

## Presentation Points

- The demo is not mock-only: the core recommender is a persisted trained bundle.
- The frontend communicates with the live backend.
- Media uploads, proof uploads, and map views are wired end to end.
- Interrupted training can be resumed from checkpoints.
- The demo can be regenerated deterministically from the canonical dataset.

## Constraints

- Authentication and authorisation remain lightweight demo scaffolding.
- Whisper and CLIP are pretrained inference components rather than finetuned models.
- The recommender bundle is the only model trained on the repository’s synthetic data.
