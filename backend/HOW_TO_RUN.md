# How to Run the SocialCode Stack

This cheat sheet walks through every step to launch the backend, optional CLI utilities, the Tkinter desktop demo, and the React frontend. Follow in order on a fresh machine.

---
## 1. Prerequisites
- Windows with PowerShell
- Python 3.11 or 3.12 on PATH
- Node.js v18+ for the React frontend
- Dataset folder: `D:\SocialCode\gram_sahayta_dataset_with_locations_and_availability`
  (contains `people.csv`, `proposals.csv`, `pairs.csv`, `village_locations.csv`, `village_distances.csv`, etc.)

Project layout:
```
D:\SocialCode\
  +- Social Code Scripts            # backend code
  +- Social-Code-Hackathon-Frontend  # React frontend
  +- gram_sahayta_dataset_with_locations_and_availability
```

---
## 2. Backend setup & API server
```powershell
cd "D:\SocialCode\Social Code Scripts"
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### (Optional) retrain the model
```powershell
python m3_trainer.py ^
  --proposals "D:\SocialCode\gram_sahayta_dataset_with_locations_and_availability\proposals.csv" ^
  --people    "D:\SocialCode\gram_sahayta_dataset_with_locations_and_availability\people.csv" ^
  --pairs     "D:\SocialCode\gram_sahayta_dataset_with_locations_and_availability\pairs.csv" ^
  --out       model.pkl
```
Logs will show progress, severity detection, distance lookup warnings, and final AUC.

### Launch the REST API
```powershell
uvicorn api_server:app --reload --port 8000
```
Endpoints:
- `POST /train` (optional) to retrain with JSON payload overrides.
- `POST /recommend` used by frontend and Tkinter app.

---
## 3. Tkinter desktop demo (no web frontend)
Keep the virtualenv active:
```powershell
python tk_app.py
```
This opens a GUI where you paste the problem statement, pick village, team size, etc. Clicking **Generate Teams** calls the backend logic and prints team breakdowns in a scrollable window.

---
## 4. React frontend (presentation UI)
Open a new PowerShell window:
```powershell
cd "D:\SocialCode\Social-Code-Hackathon-Frontend\Social-Code-Hackathon"
npm install
Set-Content .env "VITE_API_BASE_URL=http://localhost:8000"
npm run dev
```
Visit the printed URL (default `http://localhost:5173`). In the coordinator dashboard modal, fill details and click **Find Teams** to see the same recommendations via the REST API.

---
## 5. Command-line quick tests
### Direct API call (PowerShell)
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/recommend" ^
  -Method Post ^
  -ContentType "application/json" ^
  -Body '{
    "proposal_text": "Broken handpump in Bhavani Kheda, urgent repair required",
    "village_name": "Bhavani Kheda",
    "task_start": "2025-11-10T09:00:00",
    "task_end": "2025-11-10T13:00:00",
    "team_size": 4,
    "num_teams": 5,
    "severity": "HIGH"
  }'
```
### CLI trainer log check
```powershell
python m3_trainer.py --help
```
Confirms arguments and the logging instrumentation.

---
## 6. Shutdown & cleanup
- In the API window: `Ctrl+C` to stop Uvicorn.
- In the frontend window: `Ctrl+C` to stop Vite.
- Deactivate virtualenv: `deactivate`

You now have multiple ways to demo the solution: REST API, Tkinter desktop app, or full React frontend backed by the same recommender.
