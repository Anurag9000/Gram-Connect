# Backend Run Guide

## Linux Setup
```bash
cd /home/anurag-basistha/Projects/Done/Gram-Connect/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
python -m pip install pytest
```

## Verification
```bash
python -m pytest tests -q
python - <<'PY'
from api_server import RecommendRequest, recommend_endpoint
res = recommend_endpoint(RecommendRequest(
    proposal_text='Urgent handpump repair needed in Village A',
    task_start='2026-01-01T10:00:00',
    task_end='2026-01-01T12:00:00',
    team_size=2,
    num_teams=1,
    auto_extract=True,
))
print({
    'severity': res.severity_detected,
    'location': res.proposal_location,
    'team_count': len(res.teams),
})
PY
```

## Run API
```bash
python -m uvicorn api_server:app --host 127.0.0.1 --port 8011
```

## Notes
- If `model.pkl` is absent, the recommender uses the runtime TF-IDF fallback.
- CSV inputs resolve from repo defaults or from `GRAM_CONNECT_*` environment variables.
- If `8000` is already in use, keep using `8011` or choose another free port.
