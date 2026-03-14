# SocialCode Runbook

## 1. Backend
```bash
cd /home/anurag-basistha/Projects/Done/Gram-Connect/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest tests -q
python -m uvicorn api_server:app --host 127.0.0.1 --port 8011
```

## 2. Frontend
In a separate terminal:
```bash
cd /home/anurag-basistha/Projects/Done/Gram-Connect/frontend
npm install
printf 'VITE_API_BASE_URL=http://127.0.0.1:8011\n' > .env
npm test -- --run
npm run typecheck
npm run lint
npm run build
npm run dev
```

## 3. Manual UI Check
- Open the Vite URL, usually `http://127.0.0.1:5173`
- Log in as coordinator with `coordinator@test.com` / `password`
- Verify:
  - dashboard loads
  - `Assign Team` opens
  - `Generate Optimal Teams` returns recommendations
  - problem submission works
- Log in as volunteer with `volunteer@test.com` / `password`
- Verify:
  - volunteer dashboard loads tasks
  - volunteer profile loads and saves

## 4. Optional Backend Path Overrides
```bash
export GRAM_CONNECT_MODEL_PATH=/path/to/model.pkl
export GRAM_CONNECT_PEOPLE_CSV=/path/to/people.csv
export GRAM_CONNECT_PROPOSALS_CSV=/path/to/proposals.csv
export GRAM_CONNECT_PAIRS_CSV=/path/to/pairs.csv
export GRAM_CONNECT_VILLAGE_LOCATIONS_CSV=/path/to/village_locations.csv
export GRAM_CONNECT_DISTANCE_CSV=/path/to/village_distances.csv
```
