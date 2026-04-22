# Canonical Recommender Model Spec

This document describes the trained model that powers volunteer-to-problem recommendations in Gram Connect.

## Purpose

The model scores how well a volunteer matches a proposed community problem. The backend uses that score to rank candidates and assemble teams that are feasible, fair, and geographically sensible.

## Persisted Artifact

- Canonical trained bundle: `backend/runtime_data/canonical_model.pkl`
- Best checkpoint: `backend/runtime_data/canonical_model.best.pkl`
- Progress checkpoint: `backend/runtime_data/canonical_model.progress.pkl`

The backend and CLI helpers always resolve to the canonical bundle path unless you are explicitly regenerating the model during training.

## Model Family

- Primary estimator: `sklearn.ensemble.GradientBoostingClassifier`
- Text encoders stored in the bundle:
  - `prop_model`
  - `people_model`
- Backend label stored in the bundle:
  - `sentence-transformers` when a transformer backend is available
  - `tfidf` when the runtime falls back to the local vectorizer path

In the current persisted demo bundle, the text backend is `tfidf`.

## Input Signals

The training pipeline builds one sample per proposal/volunteer pair from:

- proposal text
- volunteer skills / profile text
- willingness score
- willingness bias
- volunteer availability level
- volunteer home village
- proposal village
- village-to-village travel distance
- proposal severity inferred from keywords

## Feature Vector

Each pair is converted into a 7-dimensional feature vector:

1. cosine similarity between proposal and volunteer text embeddings
2. similarity weighted by volunteer willingness
3. overall willingness score
4. normalized travel distance
5. exponential distance penalty
6. normalized availability level
7. normalized severity level

The exact feature construction lives in `backend/m3_trainer.py`.

## Training Procedure

The trainer uses:

- a deterministic random seed
- a fixed train/validation split
- `warm_start=True`
- one boosting stage at a time
- validation evaluation after every stage
- checkpoint save after every stage
- best-checkpoint save whenever validation improves
- resume-from-checkpoint support

Early stopping is controlled by:

- patience: `20` non-improving boosting stages
- tolerance: `1e-4`

Important: this is boosting-stage patience, not neural-network epochs.

## What the Model Does

At runtime, the model:

- scores volunteer-proposal compatibility
- helps rank volunteers for a given problem
- feeds the team-building logic that returns recommended groups
- works with schedule and travel constraints so the final recommendation is not just text similarity

The recommender then applies downstream rules for:

- time-window availability
- weekly workload fairness
- distance decay
- severity-aware penalties
- collision-free team selection

## What the Model Does Not Do

The recommender model does not handle:

- authentication
- authorization
- image understanding
- audio transcription
- proof verification

Those are handled by other backend services, and CLIP/Whisper remain pretrained inference components.

## Relevant Code

- Training: `backend/m3_trainer.py`
- Runtime loading: `backend/recommender_service.py`
- Canonical path resolution: `backend/path_utils.py`
- Recommendation engine: `backend/m3_recommend.py`

## Practical Summary

This is a small structured ML model that ranks volunteer matches using text similarity plus fairness and geography features. It is persisted on disk, checkpointed during training, and loaded directly by the backend at runtime.
