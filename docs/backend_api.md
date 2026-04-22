# Frontend & API Contract

This document summarises every input the frontend (or a future service) can supply to the backend scripts, and every field the backend returns. Use it to wire UI controls or REST endpoints without diving into the code.

For the canonical recommender architecture and exact feature stack, see [docs/model_spec.md](model_spec.md).

---

## Training Pipeline (`m3_trainer.py`)

### Inputs
- `proposals` *(path)* – CSV with proposal text (`text|proposal_text|description|body|content`).
- `people` *(path)* – CSV with volunteer records, including skills text, willingness columns, availability string, and `home_location`.
- `pairs` *(path)* – CSV of labelled proposal–person pairs (`label|y|target`).
- Optional overrides:
  - `out` *(path, default `backend/runtime_data/canonical_model.pkl`)* – Destination for the trained model bundle.
  - `model_name` *(string, default `sentence-transformers/all-MiniLM-L6-v2`)* – Embedding model name.
  - `village_locations` *(path, default resolved from repo/env)* – Master list used to detect proposal villages.
  - `village_distances` *(path, default resolved from repo/env)* – Pairwise village distances (km + minutes).
  - `distance_scale` *(float, default `50.0` km)* – Normalisation factor for distance feature.
  - `distance_decay` *(float, default `30.0` km)* – Distance penalty decay constant (`exp(-d/decay)`).

### Outputs
- The persisted trained bundle at `backend/runtime_data/canonical_model.pkl` containing:
  - Fitted GradientBoosting classifier.
  - Embedding backends (`prop_model`, `people_model`) and backend label (`sentence-transformers` or `tfidf`).
  - Distance hyperparameters (`distance_scale`, `distance_decay`).
  - The pipeline implicitly encodes availability levels, severity scores, and distance penalties during training.
- Intermediate checkpoint artefacts are also written during training:
  - `canonical_model.progress.pkl` after each boosting stage.
  - `canonical_model.best.pkl` when validation improves.
  - The final canonical bundle is rewritten from the best checkpoint at the end of training.

---

## Recommendation Workflow (`m3_recommend.py`)

### Inputs
Core parameters:
- `model` *(path)* – The persisted trained bundle from `m3_trainer.py`.
- `people` *(path)* – Volunteer roster CSV (same schema as training).
- Proposal data *(one of)*:
  - `proposal_text` *(string)* – Inline description.
  - `proposal_file` *(path)* – Text file with the description.
- Time window:
  - `task_start` *(ISO-8601 string)* – Assignment start time.
  - `task_end` *(ISO-8601 string)* – Assignment end time.

Skill requirements:
- `required_skills` *(list of strings)* – Explicit skills (optional).
- `skills_json` *(path)* – JSON file with `["skill", ...]` or `{"skills":[...]}`.
- `auto_extract` *(flag)* – Extract skills from proposal text using the skill extractor.
- `threshold` *(float, default `0.25`)* – Cosine threshold for auto extraction.

Fairness & availability:
- `schedule_csv` *(path)* – Existing schedule with columns `person_id,start,end[,hours]` to avoid clashes and track weekly hours.
- `weekly_quota` *(float, default `5.0` hours)* – Weekly hour budget before overwork penalty.
- `overwork_penalty` *(float, default `0.1`)* – Willingness deduction per hour above quota.
- `village_locations` *(path, default resolved from repo/env)* – Village list for proposal location inference.
- `distance_csv` *(path, default resolved from repo/env)* – Distance table for travel penalties.
- `distance_scale` *(float, default `50.0` km)* – Scale used when normalising distance.
- `distance_decay` *(float, default `30.0` km)* – Decay constant for distance penalty.
- `severity` *(enum: LOW|NORMAL|HIGH, optional)* – Manual override for automatic severity detection.

Team construction:
- `out` *(path, default `teams_m3.csv`)* – Output CSV file.
- `tau` *(float, default `0.35`)* – Coverage threshold used in similarity metrics.
- `soft_cap` *(int, default `6`)* – Maximum team size considered during greedy selection.
- `topk_swap` *(int, default `10`)* – Number of alternate volunteers inspected for 1-swap variants.
- `k_robust` *(int, default `1`)* – Required robustness level (team survives removal of up to `k` members).
- `lambda_red` *(float, default `1.0`)* – Redundancy penalty weight.
- `lambda_size` *(float, default `1.0`)* – Team-size penalty weight.
- `lambda_will` *(float, default `0.5`)* – Willingness reward weight.
- `size_buckets` *(string, default `small:2-10:10,medium:11-50:10,large:51-200:10`)* – Comma-separated `label:min-max:limit` rules for returning top teams per size bracket.

### Outputs
- Primary output: CSV (`out`) with columns  
  `rank`, `team_ids`, `team_names`, `team_size`, `goodness`, `coverage`, `k_robustness`, `redundancy`, `set_size`, `willingness_avg`, `willingness_min`.
- Log messages (stdout) include:
  - Detected proposal severity (and override if supplied).
  - Detected proposal village (or warning if not found).
  - Count of volunteers excluded due to schedule conflicts.
- No secondary files are written. Volunteers are guaranteed to appear in at most one team for the specified time window; lower-ranked teams are recomputed if a member was already assigned.
- If the configured `model` file does not exist, the backend fails closed. The demo bootstrap is responsible for generating and persisting the canonical trained bundle before serving requests.

---

## Skills Extraction (`embed_skills_extractor.py`)

### Inputs
- `text` *(string)* or `file` *(path)* – Requirement text to analyse.
- Optional:
  - `out` *(path, default `skills.json`)* – Destination JSON file.
  - `threshold` *(float, default `0.25`)* – Cosine threshold to accept skills.
  - `fallback_if_empty` *(flag)* – Use fallback skills when extraction yields none.
  - `extra_skills_json` *(path)* – JSON to extend the canonical skill bank.

### Outputs
- JSON file containing the extracted skills: either `["skill", ...]` or `{"skills":[...]}` depending on context.

---

## Exhaustive Team Builder (`team_builder_embeddings.py`)

### Inputs
- `skills` *(path)* – JSON list of required skills.
- `students` *(path)* – CSV roster with `student_id`, `name`, `skills`, willingness columns.
- Optional tuning:
  - `out` *(path, default `teams.csv`)*.
  - `topk` *(int, default `10`)*.
  - `tau` *(float, default `0.35`)*.
  - `k_robust` *(int, default `1`)*.
  - `lambda_red`, `lambda_size`, `lambda_will` *(floats, defaults `1.0`, `1.0`, `0.5`)*.

### Outputs
- CSV with the top teams (`team_ids`, `team_names`, `goodness`, coverage metrics, willingness aggregates).

---

## Notes for Frontend Integration
- All time values must be ISO-8601. The backend normalises to UTC and prevents overlapping assignments.
- Availability penalties follow a fixed heuristic: HIGH severity penalises “generally” (moderate) and “rarely” (heavy); NORMAL penalises “rarely”; LOW applies no penalty.
- Distance penalties depend on the Gram Sahayta village tables; point the CLI to alternative files if the geography changes.
- Weekly workload fairness works by tracking hours in `schedule_csv`. Provide cumulative shifts to enforce the quota.
- All weight parameters (`lambda_*`, `distance_*`, `overwork_penalty`, etc.) are safe knobs for A/B testing fairness and coverage trade-offs.
- FastAPI request bodies pass parsed datetimes into the backend; the current backend accepts both ISO strings and native `datetime` values.
