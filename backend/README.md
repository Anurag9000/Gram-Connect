# Gram Connect Backend — Specification

This document defines the backend runtime contract for Gram Connect.

The team recommendation engine is **Nexus** — a deterministic, interpretable scoring system with no ML model, no embeddings, and no training data. It replaces the previous LightGBM/embedding pipeline entirely.

---

## Architecture Overview

```
proposal_text + village_name
        │
        ▼
  extract_required_skills()       ← keyword → skill map
        │
        ▼
  score_volunteer() for every v   ← DOMAIN × WILL × AVAIL × PROX × FRESH
        │
        ▼
  _build_one_team()               ← greedy marginal-coverage selection
        │
        ▼
  _format_team()                  ← team metrics + ranking
        │
        ▼
  /recommend API response
```

---

## The Nexus Scoring Formula

```
SCORE(v, T) = DOMAIN(v,T) × WILL(v) × AVAIL(v,T) × PROX(v,T) × FRESH(v)
```

All factors are in [0, 1]. The formula is **multiplicative** — any factor near zero
eliminates the volunteer regardless of other strengths.

| Factor | Formula | What it captures |
|--------|---------|-----------------|
| **DOMAIN** | `(exact_skill_hits + 0.5 × partial_hits) / |required|` | Skill-set overlap with task requirements |
| **WILL** | `sigmoid(willingness_eff + willingness_bias − 1)` | Volunteer motivation and engagement |
| **AVAIL** | `{immediately:1.0, generally:0.7, rarely:0.35}` | Categorical availability level |
| **PROX** | `exp(−distance_km / λ)` where λ ∈ {25,40,65} by severity | Proximity to problem village |
| **FRESH** | `max(0, 1 − 0.1 × overwork_hours)` | Not burnt out from current workload |

### Distance decay by severity

| Severity | λ (km) | Rationale |
|----------|--------|-----------|
| LOW | 25 | Stay local |
| NORMAL | 40 | Balanced reach |
| HIGH | 65 | Willing to travel far for emergencies |

### Team building

```
effective_score(c) = SCORE(c)
    × (1 + 1.5 × new_skill_fraction)     ← coverage bonus
    × (1 − 0.3 × redundant_skill_fraction) ← redundancy penalty
```

Each alternative team is built from a disjoint volunteer pool (team N excludes all members of teams 1…N−1).

### Team ranking

```
team_score = coverage_fraction × geometric_mean(member scores) − 0.003 × avg_distance_km
```

Teams sorted by `(coverage, team_score)` descending — domain relevance first.

---

## `nexus.py`

Core scoring engine. No external dependencies beyond the Python stdlib.

**Key functions:**

- `extract_required_skills(text)` — keyword→skill map, returns `List[str]`
- `estimate_severity(text)` → `int` (0=LOW, 1=NORMAL, 2=HIGH)
- `score_volunteer(v, required, location, distance_lookup, severity)` → enriched dict
- `_build_one_team(scored_pool, required, target_size, excluded_ids)` → `List[Dict]`
- `run_forge(config: NexusConfig)` → API-compatible response dict

**NexusConfig fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `people_csv` | required | Volunteer roster CSV |
| `proposal_text` | required | Raw proposal text |
| `village_locations` | required | Village list CSV |
| `distance_csv` | required | Pairwise distance CSV |
| `team_size` | `None` | Fixed team size (falls back to `soft_cap`) |
| `num_teams` | `3` | Alternative teams to generate |
| `soft_cap` | `6` | Max team size when `team_size` unset |
| `severity_override` | `None` | Force severity (`LOW\|NORMAL\|HIGH`) |
| `weekly_quota` | `5.0` | Hours/week threshold before overwork penalty |
| `overwork_penalty` | `0.1` | Deduction per excess hour |
| `auto_extract` | `True` | Auto-extract required skills from text |
| `proposal_location_override` | `None` | Override village detection |

---

## `recommender_service.py`

Thin bridge: `RecommenderService.generate_recommendations(config_dict)` → calls `run_forge()`.

- **No model loading.** `set_model_path()` is a no-op kept for API compatibility.
- Pre-loads distance lookup and village names once at startup.

---

## `api_server.py`

FastAPI service. Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/volunteers` | List all seeded volunteers |
| `GET` | `/problems` | List all problems with matches |
| `POST` | `/problems` | Submit new problem |
| `POST` | `/recommend` | Generate team recommendations via Nexus |
| `POST` | `/assign` | Assign volunteer(s) to a problem |
| `DELETE` | `/problems/{id}` | Delete (nuke) a problem |
| `PUT` | `/problems/{id}/status` | Update problem status |
| `POST` | `/unassign` | Remove a volunteer from a problem |

---

## Boot Sequence

```bash
python generate_canonical_dataset.py   # regenerate CSVs (480 volunteers, 180 proposals)
python -m pytest tests/test_forge_utils.py -q   # verify Nexus scoring logic
python -m uvicorn api_server:app --host 127.0.0.1 --port 8011
```

No model training step required. Every restart seeds fresh from CSVs.

---

## What Was Removed

| Removed | Reason |
|---------|--------|
| `m3_trainer.py` calls | No ML training needed |
| `canonical_model.pkl` | No ML model |
| `pairs.csv` labels | No training data |
| LightGBM inference | Replaced by arithmetic scoring |
| Embedding models (`prop_model`, `people_model`) | Cross-model cosine was mathematically invalid |
| `k_robustness` metric | Meaningless for small teams; deprecated |
| `similarity_coverage` (cosine-based) | Replaced by direct string-match coverage |

---

## Dataset

`generate_canonical_dataset.py` writes to `data/`:

| File | Contents |
|------|----------|
| `people.csv` | 480 volunteers (12 base profiles × 40 variants each) |
| `proposals.csv` | 180 problems (12 base × 15 variants) |
| `village_locations.csv` | 5 villages with lat/lng |
| `village_distances.csv` | All pairwise km + travel time |
| `schedule.csv` | Volunteer availability windows |
| `runtime_profiles.csv` | Auth profile seeds |

Volunteer home locations are distributed across all 5 villages (~96 per village).

---

*Keep this document in sync with any API or NexusConfig contract changes.*
