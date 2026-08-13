# PawPredict 0.4 upgrade notes

## Run this migration
Run **only** `database/migrations/006_calendar_observation_ml.sql` against the database that already has migrations 002–005.

Migration 006 adds:
- observation-period potty evidence and likely-state fields;
- camera-check metadata;
- `scheduled_items` for future vet/grooming/bath/care reminders.

The repository copy of migration 005 was also corrected to match the actual `event_types` schema. Do not rerun 005 on a database where it has already been applied.

## New product behavior
- Calendar tab with month navigation, historical day drill-down, and future care items.
- Important future care entries remain separate from completed event logs.
- Quick Log detail fields expand immediately under the selected button.
- Overnight sleep is treated as an interval and split across calendar dates for analytics.
- Unobserved periods can record interval-level pee/poop evidence without inventing timestamps.
- Insights includes observation coverage and interval-potty evidence quality metrics.
- UI received a cohesive accent-driven visual polish.

## ML workspace
`ml/` contains the initial design and baseline code for predicting potty in the next 10 minutes. Keep collecting data before treating fitted probabilities as reliable. Negative training windows should exclude unobserved time.

## Local setup
The handoff ZIP intentionally excludes `.env`, `node_modules`, `dist`, `.git`, caches, and OS metadata. Keep your existing local `.env` files and run `npm install` in `frontend/` after replacing files.
