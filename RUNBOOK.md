# SocialCode Runbook (Backend + Frontend)

Follow these steps on a fresh machine to train the model, launch the API, and run the frontend UI for live team recommendations.

> **Assumptions**
>
> - Repository layout:
>   - Backend: `D:\SocialCode\Social Code Scripts`
>   - Dataset: `D:\SocialCode\gram_sahayta_dataset_with_locations_and_availability`
>   - Frontend: `D:\SocialCode\Social-Code-Hackathon-Frontend\Social-Code-Hackathon`
> - Python 3.11/3.12 available on PATH.
> - Node.js (v18+) installed for the frontend.

---

## 1. Clone or update repositories

```powershell
# Backend repo

Ensure the dataset folder `data/` is present and contains:
```
availability_legend.csv
pairs.csv
people.csv
proposals.csv
README_gram_sahayta_dataset.txt
village_distances.csv
village_locations.csv
```

---

## 2. Backend setup

### 2.1 Create and activate virtual environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
```

### 2.2 Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.3 Train the model (optional if you reuse an existing `model.pkl`)

```powershell
python -m uvicorn api_server:app --help  # sanity check import works

# Run training (will read dataset defaults automatically)
python -c "from m3_trainer import TrainingConfig, train_model; train_model(TrainingConfig(
    proposals=r'../data/proposals.csv',
    people=r'../data/people.csv',
    pairs=r'../data/pairs.csv',
    out='model.pkl'
))"
```
Logging will print progress (data load counts, severity/location detection, AUC, etc.). If you already trust the bundled `model.pkl`, you can skip this retrain.

### 2.4 Launch API server

```powershell
uvicorn api_server:app --reload --port 8000
```

Endpoints now available:
- `POST http://localhost:8000/train` – retrain with optional overrides.
- `POST http://localhost:8000/recommend` – run inference (used by frontend).

---

## 3. Frontend setup

### 3.1 Install dependencies

```powershell
cd frontend
npm install
```

### 3.2 Configure API URL

Create `.env` (same directory) with:
```
VITE_API_BASE_URL=http://localhost:8000
```
Adjust host/port if the API runs elsewhere.

### 3.3 Run dev server

```powershell
npm run dev
```

Open the printed URL (default `http://localhost:5173`). The coordinator dashboard “Find Teams” button now calls the backend recommender, shows severity/location summary, and lists top teams with willingness metrics.

---

## 4. Full end-to-end test

1. Backend running (`uvicorn …`).
2. Frontend running (`npm run dev`).
3. On the coordinator dashboard:
   - Enter problem description, choose village from dropdown, tweak team size/number or severity as needed.
   - Click “Find Teams” to fetch live recommendations.
   - Review the summary (severity, inferred location) and the ranked teams with member details.

You’re ready for the hackathon presentation.
