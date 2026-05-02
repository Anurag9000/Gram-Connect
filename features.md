# Features

This document records the features that are already implemented in the current repository state.
It is meant to be an implementation inventory, not a product roadmap.

## Core Platform

- FastAPI backend in `backend/api_server.py`.
- React + Vite frontend in `frontend/src/App.tsx`.
- Role-based navigation and page routing for villagers, volunteers, coordinators, supervisors, and partners.
- Internationalization support across the frontend with locale bundles.
- Management studio for platform records, confirmations, audits, exports, policy, and AI-assisted admin workflows.
- Installable PWA shell with offline caching for the frontend shell.

## Data and Persistence

- Postgres-backed runtime store for live problems, volunteers, profiles, media assets, metadata, and learning events.
- Seed catalog ingestion from the canonical CSV datasets into Postgres.
- Vector-capable storage via `pgvector` for seed records, problems, and learning events.
- Runtime media storage under `backend/runtime_data/media/`.
- Runtime state synchronization and bootstrapping logic.

## Villager Intake

- Villager onboarding flow for basic profile capture.
- Problem submission form with:
  - manual title, description, category, village, and address entry
  - auto category inference
  - auto severity inference
  - image upload and image analysis
  - audio recording and transcription
  - extracted visual tags
  - live instant guidance while typing
- Duplicate problem detection during submission, with auto-attachment of likely repeats to an existing open case.
- WhatsApp webhook intake path for problem creation from message text and media context.

## Volunteer Workflows

- Volunteer login and profile page.
- Volunteer skill editing and availability updates.
- Live reassignment when volunteer state changes.
- Volunteer task list and task detail view.
- Proof-of-work submission with before/after media and verification.
- Jugaad repair assistant for temporary field fixes using uploaded photos and local materials.
- Supervisor login and dashboard for escalation, seasonal risk, maintenance, hotspot, and campaign oversight.
- Partner login and dashboard for weekly briefing, public accountability, and program-level monitoring.

## Coordinator Workflows

- Coordinator login and dashboard.
- Problem queue with status filtering and search.
- Manual assignment flow.
- AI-assisted team generation flow using the Nexus recommender.
- Problem edit, delete, unassign, and status update operations.
- Problem media review and proof review.
- Case timeline view for full audit trails on individual problems.
- Map-based operational view with village autocomplete and live filtering.
- Public read-only status board for residents and coordinators.
- Operations intelligence panel with escalations, route clustering, playbooks, inventory, and volunteer reliability.
- Planning and prevention panels for seasonal risk, preventive maintenance, hotspot mapping, and campaign mode.
- Evidence comparison view for completed cases with before/after proof data.
- Platform studio entry point for asset lifecycle, procurement, privacy, certification, scheduling, training, community signals, analytics, and admin exports.
- Community broadcast composer for village-targeted and volunteer-targeted announcements with tags, media, and scheduling.
- Resident feedback analytics for villager-rated volunteer work, reopen responses, and village-level satisfaction summaries.
- Repeat-breakdown analytics for tracking how often villages or asset classes recur, fail again, or cluster over time.
- Community event scheduling and broadcast workflows for water camps, repair days, sanitation drives, awareness meetings, and ad-hoc notices.

## AI and Recommendation Layer

- Nexus recommendation engine with severity-aware volunteer scoring.
- Required-skill extraction from problem text.
- Distance, willingness, availability, and freshness-aware matching.
- Team construction with coverage and redundancy scoring.
- Recommendation API endpoint for coordinator dispatch.
- Multimodal services for:
  - audio transcription
  - image analysis
  - proof verification
  - severity inference
  - WhatsApp problem parsing
  - Jugaad fix generation
  - instant reporter guidance

## Conversational Analytics

- Gram-Sahayaka conversational analytics panel.
- Natural-language coordinator query handling.
- Overview statistics for problems and volunteers.
- Village-level complaint summaries.
- Idle volunteer lookup by skill and location.
- Risk clustering for outbreak-like and systemic infrastructure patterns.
- Semantic clustering over recent problem reports.
- Weekly operational briefing with root-cause graph signals.
- Duplicate-aware routing and follow-up feedback handling for reopened or unresolved cases.

## Notifications and Learning Loop

- Learning event recording for major writes and analytics requests.
- Problem resolution notifications.
- Team assignment notification path.
- Resident follow-up feedback capture after closure, with reopen-on-still-broken handling.
- Recent learning events query endpoint.

## Field Operations

- Offline-first volunteer draft queue for proof submissions and Jugaad requests.
- Reusable solved-case playbooks derived from completed problems and proof submissions.
- Village/volunteer inventory records for spare parts and tools.
- Escalation scanning by severity and problem age.
- Volunteer reliability scoring from recent completion and backlog patterns.
- Route optimization suggestions that cluster open work by village.
- Preventive scheduling and hotspot detection for recurring field issues.
- Community broadcast surfaces in the coordinator dashboard, volunteer dashboard, public status board, and platform studio.

## Developer and Verification Tooling

- Canonical dataset generation scripts.
- Recommender training and verification scripts.
- Backend test suite coverage for the main API and service layers.
- Frontend unit tests and typecheck coverage.
- End-to-end browser test scaffolding.

## Implemented But Demo-Scoped

- Authentication remains lightweight and demo-oriented.
- SMS delivery is currently mocked by logging in `backend/notification_service.py`.
- Deployment infrastructure and secret management are intentionally left out of scope.

## Completion Note

The repository should be treated as feature-complete for its current scope. Remaining work, if any, belongs to future expansion rather than completing a partial baseline.
