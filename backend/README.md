# Gram Connect Backend CLI and Runtime Specification

This document defines the backend command-line surface and runtime contract for Gram Connect. The canonical persisted model is stored at `backend/runtime_data/canonical_model.pkl`, and repository defaults resolve from the checked-in dataset or from `GRAM_CONNECT_*` environment variables.

For a concise description of the recommender architecture, feature stack, and checkpointing policy, refer to [docs/model_spec.md](../docs/model_spec.md).

For Linux systems with NVIDIA GPU support, install PyTorch before the repository requirements:

```bash
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

The verified backend workflow is:

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
python generate_canonical_dataset.py
python -m pytest tests -q
python run_full_verification.py
python -m uvicorn api_server:app --host 127.0.0.1 --port 8011
```

The canonical dataset generator writes `people.csv`, `proposals.csv`, `pairs.csv`, `village_locations.csv`, `village_distances.csv`, `schedule.csv`, and `runtime_profiles.csv` into the repository `data/` directory. The API runtime seeds from those files and persists live state to `backend/runtime_data/app_state.json`.

---

## `m3_trainer.py`

Train the gradient-boosted classifier used for volunteer-to-proposal compatibility scoring.

- `--proposals` **(required)**: CSV with proposal text (`text|proposal_text|description|body|content`).
- `--people` **(required)**: CSV with volunteer profiles, willingness signals, availability category, and home village.
- `--pairs` **(required)**: CSV of labelled proposal-person pairs (`label|y|target`).
- `--out` (default `backend/runtime_data/canonical_model.pkl`): Output bundle containing the classifier and embedding backends.
- `--model_name` (default `sentence-transformers/all-MiniLM-L6-v2`): Embedding model used to train the persisted bundle.
- `--village_locations` (default resolved from repo/env): Master village list for proposal location parsing.
- `--village_distances` (default resolved from repo/env): Pairwise village distances, including kilometres and travel minutes.
- `--distance_scale` (default `50.0` km): Normalisation scale so `distance_km / distance_scale` is clipped to `[0, 1]`.
- `--distance_decay` (default `30.0` km): Decay constant for the distance penalty `exp(-distance / distance_decay)` applied to willingness.
- `--resume_from_checkpoint` / `--no-resume_from_checkpoint`: Resume from the best saved checkpoint by default, or force a clean run.
- `--checkpoint_every` (default `1`): Save the current stage checkpoint every `N` boosting steps.

The trainer identifies the village referenced in each proposal, estimates severity (`LOW`, `NORMAL`, or `HIGH`) from keywords, maps availability strings to levels, and augments the feature matrix with distance- and severity-aware penalties. The chosen distance hyperparameters are stored in the persisted bundle so the recommender remains internally consistent.

During training the script writes:

- `canonical_model.progress.pkl` after every boosting stage
- `canonical_model.best.pkl` whenever validation improves

If a run is interrupted, rerunning the trainer resumes from the best saved stage by default and then writes the final canonical bundle back to `backend/runtime_data/canonical_model.pkl`.

---

## `m3_recommend.py`

Build teams for a new proposal while respecting skills, willingness, geography, availability fairness, pre-existing schedules, and weekly workload ceilings.

- `--model` **(required)**: Path to the persisted trained bundle.
- `--proposal_text` / `--proposal_file`: Inline description or text file path for the problem statement.
- `--people` **(required)**: Volunteer roster (flexible headers for IDs, text/skills, willingness, availability, and home location).
- `--required_skills`: Explicit list of skills (overrides auto extraction).
- `--skills_json`: JSON file with `["skill", ...]` or `{"skills":[...]}`.
- `--auto_extract`: Enable automatic skill extraction.
- `--threshold` (default `0.25`): Cosine threshold for auto extraction.
- `--out` (default `teams_m3.csv`): Output CSV.
- `--tau` (default `0.35`): Coverage threshold for similarity metrics.
- `--task_start` **(required)** / `--task_end` **(required)**: ISO-8601 timestamps defining when the task runs.
- `--village_locations` (default resolved from repo/env): Village list to locate the proposal.
- `--distance_csv` (default resolved from repo/env): Distance table for travel penalties.
- `--distance_scale` (default `50.0` km) / `--distance_decay` (default `30.0` km): Match the training settings.
- `--severity` (`LOW|NORMAL|HIGH`): Override the automatic severity classifier.
- `--schedule_csv`: Existing volunteer schedule (`person_id,start,end[,hours]`) to avoid clashes.
- `--weekly_quota` (default `5.0` hours): Weekly hour budget before overwork penalties apply.
- `--overwork_penalty` (default `0.1`): Willingness deduction per hour above the weekly quota.
- `--soft_cap` (default `6`): Maximum team size considered during greedy selection.
- `--topk_swap` (default `10`): Number of alternatives inspected for one-swap improvements.
- `--k_robust` (default `1`): Required robustness level, meaning the team survives the loss of any `k` members.
- `--lambda_red`, `--lambda_size`, `--lambda_will` (defaults `1.0`, `1.0`, `0.5`): Weights for redundancy, size, and average willingness in the goodness score.
- `--size_buckets` (default `small:2-10:10,medium:11-50:10,large:51-200:10`): `label:min-max:limit` rules for how many teams to return per size band.

Runtime pipeline:

1. Detect the proposal village and severity. `HIGH` severity penalises "generally available" volunteers moderately and "rarely available" volunteers heavily; `NORMAL` penalises "rarely available" only.
2. Drop volunteers already booked during the specified window (`--schedule_csv`).
3. Apply weekly workload penalties via `--weekly_quota` and `--overwork_penalty`.
4. Apply distance decay (`exp(-distance / distance_decay)`) and severity-aware penalties to willingness before scoring with the model.
5. Greedily assemble the best team under `--soft_cap`, then explore one-swap variants.
6. Enforce per-bucket top-k limits via `--size_buckets`.
7. Remove any volunteer who appears in multiple recommended teams; the lower-ranked team is recomputed without them so the final list is collision-free.

Output columns include `team_size`, `goodness`, `coverage`, `k_robustness`, `redundancy`, `set_size`, `willingness_avg`, and `willingness_min`. Distance and severity effects are reflected in the aggregated willingness metrics and goodness scores.

If the configured model path does not exist, the runtime API fails closed. The demo bootstrap and `run_full_verification.py` are responsible for creating the canonical trained bundle before serving recommendations.

The repository also includes `run_full_verification.py`, which performs a real training run, validates seeded data integrity, verifies schedule-aware inference, and exercises `/recommend`, `/analyze-image`, and `/transcribe` using repository fixtures.

---

## `team_builder_embeddings.py`

Exhaustive enumerator for small rosters, useful for validation or debugging.

- `--skills` **(required)**: JSON list of required skills.
- `--students` **(required)**: CSV roster with willingness columns.
- `--out` (default `teams.csv`).
- `--topk` (default `10`).
- `--tau` (default `0.35`).
- `--k_robust` (default `1`).
- `--lambda_red`, `--lambda_size`, `--lambda_will` (defaults `1.0`, `1.0`, `0.5`): Align weights with the recommender for comparable scores.

Outputs mirror the recommender metrics, including willingness averages and minima.

---

## `embed_skills_extractor.py`

Map free-form proposal text to canonical Gram Sahayta skill phrases.

- `--text` or `--file`: Inline text or path to a `.txt` file.
- `--out` (default `skills.json`): Destination JSON.
- `--threshold` (default `0.25`): Cosine threshold to accept a skill.
- `--fallback_if_empty`: Use the domain fallback skill list when nothing clears the threshold.
- `--extra_skills_json`: JSON with `{"skills": [...], "synonyms": {...}}` to extend the skill bank.

---

## Legacy Helpers

- `m3_recommend_early.py`: Early recommender variant with flags `--model`, `--proposal_text`, `--people`, `--required_skills`, `--out`, `--tau`, and `--soft_cap`.
- `embed_skills_extractor_early.py`: Minimal extractor with flags `--text`, `--file`, and `--out`. Prefer the main extractor for production.

---

## Integration Notes

- CLI flags are API-ready. Dataset paths can be overridden with `GRAM_CONNECT_*` environment variables, but the canonical model bundle always resolves to `backend/runtime_data/canonical_model.pkl`.
- Time arguments must be ISO-8601; the scheduler converts them to UTC and maintains collision-free assignments.
- Severity and availability penalties follow a fixed heuristic: `HIGH` penalises "generally" and "rarely"; `NORMAL` penalises "rarely"; `LOW` applies no penalty. Override `--severity` or adjust the source if policy changes.
- Distance penalties depend on the supplied village assets; point the CLI to different CSVs if the geographic context changes.
- Goodness weights (`lambda_*`), workload penalties, and distance parameters are configurable without code changes.

Keep this document synchronized with any CLI or runtime contract change; downstream services use it as the parameter specification.
