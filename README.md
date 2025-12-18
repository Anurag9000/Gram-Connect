# SocialCode (SahayAI) 🚀

**SocialCode** is an AI-powered, multi-modal volunteer-need matching platform designed to empower NSS units and rural communities. By intelligently connecting student skills with real-world village needs, SocialCode streamlines the process of community development through data-driven matching and fairness-aware algorithms.

---

## 🌟 The Vision: Truly Multi-Modal

SocialCode is designed to break communication barriers in rural areas by processing needs across multiple modalities:

- 🎙️ **Audio**: Voice-to-text processing for villagers to report issues via voice notes or calls.
- 🖼️ **Image**: Visual recognition (using CLIP-inspired embeddings) to analyze infrastructure damage or environmental issues from photos.
- 📹 **Video**: Summarization of community meetings or visual evidence of project progress.
- ✍️ **Text**: Natural language understanding of project proposals and volunteer profiles.

---

## 🔥 Key Features

### 1. M3 Recommender Engine
Our **Multi-Modal, Multi-Metric (M3) Recommender** goes beyond simple keyword matching. It uses:
- **Sentence Embeddings**: Captures the semantic intent of both proposals and volunteer skills.
- **ULTRA Framework**: Optimizes for Coverage, Robustness, Redundancy, and Set-Size.
- **Fairness-Aware Metrics**: Accounts for volunteer willingness, weekly workload quotas, and availability patterns.

### 2. Integrated Metrics & Mathematical Logic
The system's core "Goodness Score" is dynamically adjusted based on four critical real-world factors:

| Metric | Implementation Logic | Impact on Recommendation |
| :--- | :--- | :--- |
| **Availability** | Mapped from `rarely`, `generally`, or `immediately` available. | Higher availability reduces "Selection Penalty" in high-urgency tasks. |
| **Priority (Severity)** | Auto-detected from text or manual override (LOW to HIGH). | Amplifies availability penalties; HIGH severity demands immediate responders. |
| **Distance** | Geodesic distance between volunteer home and village location. | Applies an exponential decay: $W_{adj} = W \cdot e^{(-d/decay)}$, prioritizing local impact. |
| **Work Hours** | Tracks total hours assigned vs. Weekly Quota (default 5h). | Applies an `overwork_penalty` for assignments exceeding the quota to prevent burnout. |

### 3. Geo-Spatial Awareness
- **Distance Penalties**: Automatically prioritizes volunteers closer to the village in need.
- **Village-Specific Fallbacks**: Intelligent skill extraction tailored to rural contexts (WASH, MGNREGA, Irrigation).

### 3. Severity Detection
- **AI-Driven Priority**: Automatically classifies project severity (LOW, NORMAL, HIGH) to ensure critical needs (e.g., water contamination or infrastructure collapse) are prioritized.

---

## 🛠️ Architecture

SocialCode consists of three main components:

1. **Backend (Python/FastAPI)**:
   - Houses the `M3 Recommender` and `M3 Trainer`.
   - APIs for training models and generating real-time team recommendations.
   - Intelligent skill extraction and severity classification.

2. **Frontend (Vite/React)**:
   - Clean, intuitive Coordinator Dashboard.
   - "Find Teams" interface with live recommendations.
   - Multi-modal input support (Voice/Image).

3. **Inbound Data Layer**:
   - Supports CSV-based volunteer rosters and village datasets.
   - Dynamic scheduling logic to prevent volunteer overwork.

---

## 🚀 Getting Started
## 🏗️ Technical Architecture
The project is organized into a clean, modular structure for maximum portability:

- **`backend/`**: Python FastAPI service handling NLP, embeddings, and the M3 Recommender core.
- **`frontend/`**: Vite + React + TypeScript dashboard with a premium design system.
- **`data/`**: Consolidated datasets including village locations, distances, and volunteer rosters.
- **`docs/`**: Technical whitepapers and API contracts.

## 🛠️ Getting Started

### Backend Setup
1. `cd backend`
2. Create virtual environment: `python -m venv venv`
3. Activate: `.\venv\Scripts\activate`
4. Install: `pip install -r requirements.txt`
5. Run: `uvicorn api_server:app --reload`

### Frontend Setup
1. `cd frontend`
2. Install: `npm install`
3. Run: `npm run dev`
   ```
3. Set up environment variables (`.env`):
   ```
   VITE_API_BASE_URL=http://localhost:8000
   ```
   ```powershell
   npm run dev
   ```

---

## 📊 Dataset
The project utilizes the **Gram Sahayta Dataset**, which includes:
- `proposals.csv`: 2–4 sentence project descriptions.
- `people.csv`: Volunteer profiles with willingness and availability levels.
- `village_locations.csv` & `village_distances.csv`: Geo-spatial data for proximity-based matching.

---

## 🏆 Innovation & Impact
SocialCode (SahayAI) addresses the organizational chaos in rural service by providing a **systematic, AI-driven bridge** between campus talent and village development. It is engineered for impact, fairness, and accessibility.

---

*Developed for the Social Code Hackathon.*
