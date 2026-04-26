# Gram-Connect Features

Gram-Connect is a full-stack platform designed to crowdsource community problem reporting, auto-classify urgency, and intelligently route tasks to local volunteers and coordinators.

## 🛠 Tech Stack
*   **Frontend:** React, TypeScript, Vite, Tailwind CSS
*   **Backend:** Python, FastAPI, Pydantic, Scikit-learn, LightGBM/XGBoost
*   **Database:** Supabase (PostgreSQL)

## 🌟 Key Features

### 1. The Nexus (AI Recommender Engine)
*   **Severity-Aware Scoring:** Weights constraints (distance, availability, willingness) dynamically based on task urgency (HIGH, NORMAL, LOW).
*   **Two-Phase Team Builder:** Guarantees rare-skill experts are matched to multi-domain tasks before filling the rest of the team with high-quality generalists.
*   **Data-Driven Exponents:** Scoring exponents are derived from 150k synthetic samples, evaluated via a Multi-Model ML Shootout (LightGBM, XGBoost), and extracted via normalized SHAP values.

### 2. Auto-Inference Pipeline
*   **Smart Submissions:** Users type a description of the problem. On blur, the platform automatically infers:
    *   `Severity`: Is this an emergency or a routine fix?
    *   `Category`: Routes the task into 1 of 7 strict, non-overlapping domains (e.g., `water-sanitation`, `infrastructure`).
*   **Skill Extraction:** Natural Language heuristic engine converts raw task descriptions into an array of strict required skills (e.g., `plumbing`, `masonry`) for the backend.

### 3. Dedicated Dashboards
*   **Volunteer Dashboard:**
    *   View personalized, high-match task recommendations.
    *   Color-coded UI indicators for task severity (e.g., Red Alert borders for HIGH severity).
    *   Manage weekly quotas, working hours, and physical availability.
*   **Coordinator Dashboard:**
    *   Triage queues sorted automatically by the auto-inferred non-overlapping routing labels.
    *   One-click "Assemble Team" triggers the Nexus engine to generate the perfect team for multi-domain problems.
    *   Review proof-of-work uploads submitted by volunteers upon task completion.

### 4. Interactive Map & Geography
*   **Proximity-Based Routing:** Computes distance decay penalties to ensure routine tasks stay local, while expanding the search radius exclusively for emergencies.

### 5. Production Ready
*   Full API integration spanning problem submission, engine recommendations, to proof-of-completion.
*   Exhaustive test suite (`tests/test_nexus_utils.py`) verifying all edge cases of team-building and scoring algorithms.
