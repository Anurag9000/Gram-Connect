# Frontend Operational Guide

## Purpose

This document defines the local verification and development sequence for the Gram Connect frontend.

## Install and Verify

```bash
cd /home/anurag-basistha/Projects/TODO/Gram-Connect/frontend
npm install
printf 'VITE_API_BASE_URL=http://127.0.0.1:8011\n' > .env
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

## Development Server

```bash
npm run dev
```

The development server prints a local URL, typically `http://127.0.0.1:5173`.

## Backend Dependency

The frontend expects the backend API to be reachable at `http://127.0.0.1:8011` unless `VITE_API_BASE_URL` is changed.

## Demo Access Credentials

- Coordinator: `coordinator@test.com` / `password`
- Volunteer: `volunteer@test.com` / `password`

## Manual Review Items

- Coordinator dashboard loads problem records and assignment controls.
- `Assign Team` opens the assignment workflow.
- Recommendation generation returns backend-derived team suggestions.
- Problem submission reaches the backend and persists media metadata.
- Volunteer dashboard loads assigned tasks.
- Volunteer profile loads and saves successfully.
