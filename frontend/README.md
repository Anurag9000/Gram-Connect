# Frontend Run Guide

## Install and Verify
```bash
cd /home/anurag-basistha/Projects/Done/Gram-Connect/frontend
npm install
printf 'VITE_API_BASE_URL=http://127.0.0.1:8011\n' > .env
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

## Start Dev Server
```bash
npm run dev
```

Open the printed URL, usually `http://127.0.0.1:5173`.

## Expected Backend
The frontend expects the backend API to be reachable at `http://127.0.0.1:8011` unless you change `VITE_API_BASE_URL`.

## Test Logins
- Coordinator: `coordinator@test.com` / `password`
- Volunteer: `volunteer@test.com` / `password`

## Manual Checks
- Coordinator dashboard loads issues
- `Assign Team` and `Generate Optimal Teams` work
- Submit Problem sends data to the backend
- Volunteer dashboard shows tasks
- Volunteer profile loads and saves
