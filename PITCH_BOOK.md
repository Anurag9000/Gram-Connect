# Gram Connect Pitch Book

## One-Line Summary
Gram Connect is a live community-issue reporting and volunteer-assignment platform with a persisted recommender model, multimodal issue intake, map-based operations, and proof-backed task completion.

## What The Product Does
- Villagers can submit problems with text, image, and optional audio.
- The backend analyzes images and audio, persists the submission, and stores media artifacts.
- Coordinators can generate volunteer teams from the trained recommender bundle.
- Volunteers can view assignments, upload before/after proof, and complete work.
- The coordinator dashboard and map view reflect the live backend state.

## What Is Trained
- Only the recommender bundle is trained.
- The live canonical bundle is saved at `backend/runtime_data/canonical_model.pkl`.
- The bundle is built from the canonical synthetic dataset in `data/`.
- CLIP and Whisper are used as pretrained inference services only.

## Exact Training Window
- Verified canonical training ran on `2026-04-22` in the `Asia/Kolkata` timezone.
- The training started at approximately `22:13:11 IST`.
- The verified run completed at approximately `22:20:12 IST`.
- A later continuation run resumed from the best checkpoint and early-stopped again after additional boosting stages, finishing with a stronger bundle on the same canonical artifact path.

## How It Was Trained
- Entry point: `backend/run_full_verification.py`
- Trainer: `backend/m3_trainer.py`
- Model family: `GradientBoostingClassifier`
- Text backend: `tfidf` fallback was used in the verified run
- Training recipe:
  - `n_estimators=600`
  - `learning_rate=0.03`
  - `subsample=0.85`
  - `max_depth=3`
  - `validation_fraction=0.2`
  - `n_iter_no_change=20`
  - `tol=1e-4`
- The trainer now runs stage by stage with `warm_start=True`.
- After every boosting stage it writes a progress checkpoint.
- Whenever validation improves, it writes a best checkpoint.
- If a run is interrupted, the next run resumes from the best saved checkpoint by default.

## Hold-Out Metrics
- The latest evaluation uses a deterministic `70/15/15` train/validation/test split.
- Training metrics are tracked on the validation split during boosting, and final reporting is done on the held-out test split.
- On the held-out validation split from the latest persisted canonical bundle:
  - Accuracy: `0.8814`
  - ROC AUC: `0.9479`
  - Log loss: `0.2949`
- On the held-out test split from the latest persisted canonical bundle:
  - Accuracy: `0.8611`
  - ROC AUC: `0.9385`
  - Log loss: `0.3135`
- The lowest validation loss observed during the latest continuation run was `0.2949`.

## Early Stopping Behavior
- The trainer uses manual early stopping logic, not a black-box fit-only call.
- Validation is evaluated after each boosting stage.
- If validation does not improve for `n_iter_no_change` consecutive stages, the run stops early.
- In the verified training run, validation kept improving enough that the run reached the full `600` stages.
- In the continuation run, the trainer resumed from the best checkpoint, kept training until patience triggered, and stopped after the validation metric stopped improving for the configured window.
- That means early stopping is active, checkpointed, and resumable rather than a one-shot fit.

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
- There is not a finetuning corpus for Whisper or CLIP, so those remain frozen pretrained services.

## Demo Flow
1. Start the backend demo server.
2. Open the frontend.
3. Submit a problem with media.
4. Open the dashboard and generate recommendations.
5. Open the map and inspect live case locations.
6. Open the volunteer dashboard and submit proof.
7. Confirm the backend state updates everywhere.

## Verification Status
- Backend unit tests: passed
- Frontend typecheck: passed
- Frontend unit tests: passed
- Frontend production build: passed
- Full backend verification: passed

## VC Talking Points
- The demo is not mock-only: the core recommender is a persisted trained bundle.
- The frontend speaks to the live backend.
- Media uploads, proof uploads, and map views are all wired end to end.
- Interrupted training can be resumed from checkpoints.
- The demo can be regenerated deterministically from the canonical dataset.

## Honest Constraints
- Auth and authorization are intentionally left as lightweight demo scaffolding.
- Whisper and CLIP are pretrained inference components, not finetuned on repo data.
- The recommender bundle is the only model trained on the repo’s mock data.
