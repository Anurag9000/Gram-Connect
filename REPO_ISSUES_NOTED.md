# Repo Issues Noted

This file records concrete issues found during review. It is intended to be appended to as more problems are discovered.

## Confirmed Issues

### 1. Runtime state persistence is disabled
- File: [`backend/api_server.py`](./backend/api_server.py)
- Lines: around `963-1011`
- Problem: `persist_runtime_state()` only increments `STATE_VERSION` and never writes `app_state.json`.
- Problem: `load_initial_data()` contains `if False and os.path.exists(RUNTIME_STATE_JSON)`, so the saved state branch is unreachable.
- Impact: problems, profiles, media, and assignments do not reliably survive restart.

### 2. Notification wiring does not match the returned team/member shape
- File: [`backend/notification_service.py`](./backend/notification_service.py)
- Lines: around `29-46`
- Problem: `notify_team_assignment()` looks for `member.get('profile', {})`, but backend team objects usually carry `profiles` on volunteer records or omit phone data entirely.
- File: [`backend/nexus.py`](./backend/nexus.py)
- Lines: around `545-559`
- Problem: the formatted team members do not include phone numbers or nested `profile` data in a way `notify_team_assignment()` can use.
- Impact: assignment notifications are logged but effectively not sent in the normal backend flow.

### 3. Recommendation wrapper ignores several caller-controlled fields
- File: [`backend/recommender_service.py`](./backend/recommender_service.py)
- Lines: around `38-73`
- Problem: `generate_recommendations()` forwards only a subset of request fields into `NexusConfig`.
- Omitted/unused fields include `schedule_csv`, `size_buckets`, `lambda_red`, `lambda_size`, `lambda_will`, `topk_swap`, `k_robust`, and `tau`.
- Impact: callers can pass tuning values that have no effect, and schedule-based filtering is not actually wired through this path.

### 4. Problem IDs can collide under concurrent submissions
- File: [`backend/api_server.py`](./backend/api_server.py)
- Lines: around `1378-1431`
- Problem: new problems use `prob-{int(datetime.now().timestamp())}`.
- Impact: two submissions in the same second can generate the same ID, which can break updates, deletion, and frontend keys.

### 5. Audio recording is labeled as WAV without real transcoding
- File: [`frontend/src/components/AudioRecorder.tsx`](./frontend/src/components/AudioRecorder.tsx)
- Lines: around `45-49`
- Problem: the recorder creates a `Blob` with type `audio/wav` from raw `MediaRecorder` chunks.
- File: [`frontend/src/services/api.ts`](./frontend/src/services/api.ts)
- Lines: around `215-229`
- Problem: the upload path sends that blob as `recording.wav`.
- Impact: actual browser output format may differ from WAV, which can make transcription fail or behave inconsistently across browsers.

### 6. Volunteer task sorting comment does not match code
- File: [`backend/api_server.py`](./backend/api_server.py)
- Lines: around `1186-1191`
- Problem: the comment says same-severity tasks are sorted by `assigned_at` descending, but the code sorts ascending.
- Impact: older assignments may appear before newer ones.

### 7. Map recentering likely does not update the Leaflet view after selection
- File: [`frontend/src/pages/MapView.tsx`](./frontend/src/pages/MapView.tsx)
- Lines: around `82-97`
- Problem: selection updates `mapCenter` and `mapZoom`.
- File: [`frontend/src/components/ProblemMap.tsx`](./frontend/src/components/ProblemMap.tsx)
- Lines: around `31-60`
- Problem: `MapContainer` receives `center` and `zoom` as props, but react-leaflet typically uses those only on mount.
- Impact: village search may update state without visually moving the map.

## Environment Limitations

- Python test execution could not be verified here because `pytest` is not installed in the current environment.
- Some findings above are based on direct code inspection and inferred runtime behavior.

