# How to Run the SocialCode Stack

This project now resolves dataset files from the repo automatically. You can still override every path with environment variables when needed.

## Prerequisites
- Linux shell
- `python3`
- `node`

## Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn api_server:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
```

Optional path overrides:
```bash
export GRAM_CONNECT_MODEL_PATH=/absolute/path/to/model.pkl
export GRAM_CONNECT_PEOPLE_CSV=/absolute/path/to/people.csv
export GRAM_CONNECT_PROPOSALS_CSV=/absolute/path/to/proposals.csv
export GRAM_CONNECT_PAIRS_CSV=/absolute/path/to/pairs.csv
export GRAM_CONNECT_VILLAGE_LOCATIONS_CSV=/absolute/path/to/village_locations.csv
export GRAM_CONNECT_DISTANCE_CSV=/absolute/path/to/village_distances.csv
```

## Frontend
```bash
cd frontend
npm install
printf 'VITE_API_BASE_URL=\nVITE_DEV_PROXY_TARGET=http://your-backend-origin\n' > .env
npm run dev
```

If you deploy frontend and backend behind the same origin, `VITE_API_BASE_URL` can stay empty and the frontend will use relative URLs.

## Retraining
```bash
cd backend
python3 m3_trainer.py \
  --proposals "${GRAM_CONNECT_PROPOSALS_CSV}" \
  --people "${GRAM_CONNECT_PEOPLE_CSV}" \
  --pairs "${GRAM_CONNECT_PAIRS_CSV}" \
  --out "${GRAM_CONNECT_MODEL_PATH:-model.pkl}"
```
