# Frontend Operational Guide

## Purpose

This document defines the local verification and development sequence for the Gram Connect frontend.

## Install and Verify

```bash
cd /home/anurag-basistha/Projects/ToFix/Gram-Connect/frontend
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

## Current UI Scope

- Coordinator, volunteer, supervisor, partner, and public surfaces are all wired in the app shell.
- The platform studio is available for administrative workflows, platform records, confirmations, policy lookups, broadcast scheduling, and export bundles.
- The coordinator dashboard includes village feedback ratings, repeat-breakdown analytics, and recent broadcast visibility.
- The volunteer and public surfaces show targeted broadcasts for volunteers and residents respectively.
- The frontend ships with a lightweight offline-capable PWA shell.

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
- The platform studio loads and can create or inspect platform records.
- The public status board renders resident-facing status information.
