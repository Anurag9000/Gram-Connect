# Canonical Recommender Model Specification

This document describes the trained model that powers volunteer-to-problem recommendations in Gram Connect.

## Overview

The recommender scores how well a volunteer matches a proposed community problem. The backend uses that score to rank candidates and assemble teams that are feasible, fair, and geographically sensible.

## Persisted Artifact

- Canonical trained bundle: `backend/runtime_data/canonical_model.pkl`
- Best checkpoint: `backend/runtime_data/canonical_model.best.pkl`
- Progress checkpoint: `backend/runtime_data/canonical_model.progress.pkl`

The backend and CLI utilities resolve to the canonical bundle path unless a training command is being executed explicitly.

## Model Family

- Primary estimator: `sklearn.ensemble.GradientBoostingClassifier`
- Text encoders stored in the bundle:
  - `prop_model`
  - `people_model`
- Backend label stored in the bundle:
  - `sentence-transformers` when a transformer backend is available
  - `tfidf` when the runtime falls back to the local vectoriser path

The currently persisted demo bundle uses the `tfidf` backend.

## Input Signals

The training pipeline constructs one sample per proposal-volunteer pair from:

- proposal text
- volunteer skills or profile text
- willingness score
- willingness bias
- volunteer availability level
- volunteer home village
- proposal village
- village-to-village travel distance
- proposal severity inferred from keywords

## Feature Vector

Each pair is converted into a seven-dimensional feature vector:

1. cosine similarity between proposal and volunteer text embeddings
2. similarity weighted by volunteer willingness
3. overall willingness score
4. normalised travel distance
5. exponential distance penalty
6. normalised availability level
7. normalised severity level

The feature construction logic is implemented in `backend/m3_trainer.py`.

## Training Procedure

The trainer uses:

- a deterministic random seed
- a fixed train-validation split
- `warm_start=True`
- one boosting stage at a time
- validation evaluation after every stage
- checkpoint creation after every stage
- best-checkpoint persistence whenever validation improves
- resume-from-checkpoint support

Early stopping is controlled by:

- patience: `20` consecutive non-improving boosting stages
- tolerance: `1e-4`

This is boosting-stage patience rather than neural-network epoch control.

## Operational Behaviour

At runtime, the model:

- scores volunteer-proposal compatibility
- ranks volunteers for a given problem
- feeds the team-building logic that returns recommended groups
- operates in conjunction with schedule and travel constraints so the final recommendation is not solely text-similarity based

The recommender then applies downstream rules for:

- time-window availability
- weekly workload fairness
- distance decay
- severity-aware penalties
- collision-free team selection

## Scope Exclusions

The recommender model does not provide:

- authentication
- authorisation
- image understanding
- audio transcription
- proof verification

Those functions are handled by separate backend services, and CLIP and Whisper remain pretrained inference components.

## Relevant Code

- Training: `backend/m3_trainer.py`
- Runtime loading: `backend/recommender_service.py`
- Canonical path resolution: `backend/path_utils.py`
- Recommendation engine: `backend/m3_recommend.py`

## Summary

The canonical recommender is a structured gradient-boosted model that ranks volunteer matches using text similarity, fairness, and geography features. It is persisted on disk, checkpointed during training, and loaded directly by the backend at runtime.
