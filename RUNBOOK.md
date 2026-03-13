# SocialCode Runbook

## Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_server:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
```

The backend auto-discovers bundled CSVs in the repo. To point at external assets, set:
```bash
export GRAM_CONNECT_MODEL_PATH=/path/to/model.pkl
export GRAM_CONNECT_PEOPLE_CSV=/path/to/people.csv
export GRAM_CONNECT_PROPOSALS_CSV=/path/to/proposals.csv
export GRAM_CONNECT_PAIRS_CSV=/path/to/pairs.csv
export GRAM_CONNECT_VILLAGE_LOCATIONS_CSV=/path/to/village_locations.csv
export GRAM_CONNECT_DISTANCE_CSV=/path/to/village_distances.csv
```

## Frontend
```bash
cd frontend
npm install
printf 'VITE_API_BASE_URL=\nVITE_DEV_PROXY_TARGET=http://backend-origin\n' > .env
npm run dev
```

Use an empty `VITE_API_BASE_URL` when frontend and backend share one origin. Use `VITE_DEV_PROXY_TARGET` only for local dev proxying.
