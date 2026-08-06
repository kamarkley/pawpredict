# Configurable tracking implementation

## Database

Run `database/migrations/002_configurable_tracking.sql` once in the Supabase SQL editor before starting the updated API.

The migration:

- adds configurable event metadata;
- adds per-dog event preferences;
- adds reusable saved options;
- adds option, numeric value, unit, and severity fields to events;
- converts the existing Sleep event to Nap;
- replaces Vomit with Symptom;
- adds Sleep, Walk, Social, Behavior, Grooming, and Vet Visit;
- imports existing treats into saved options.

Do not rerun `database/schema.sql` against the existing database.

## Updated behavior

- Pee and Poop use a reusable potty result: Outside, Accident, Pee pad, Litter box, or custom.
- Nap and Sleep optionally accept a saved sleep location.
- Medication requires a saved medication and dosage.
- Symptom requires a saved symptom and severity from 1–10.
- Walk accepts an optional distance and unit.
- Treat, meal amount, medication, symptom, social activity, behavior, sleep location, grooming, and vet choices can be saved for reuse.
- Event types can be enabled or disabled per dog without deleting historical logs.
- Dog profile fields are editable.

## Start locally

Backend:

```bash
cd backend
source ../.venv/bin/activate
python -m fastapi dev app/main.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Observation periods (migration 003)

Run `database/migrations/003_observation_periods.sql` after migration 002.

This feature adds:
- active unobserved periods with no end time until the user returns
- completed manual periods
- reusable `OBSERVATION_REASON` options
- edit/delete/end actions
- overlap validation
- observation periods merged into Today's Timeline

Seeded reasons: Work, Errands, Daycare, Training class, With sitter, Boarding, Sleeping, and Other.

## 004 — Pages and configurable daily dashboard

Run `database/migrations/004_pages_and_dashboard.sql` after migrations 002 and 003.

This update adds:
- Today, Insights, and Settings pages using lightweight hash navigation.
- A daily stats dashboard calculated from today's events and observation periods.
- Per-dog dashboard card visibility and ordering.
- Profile, tracking choices, saved options, and dashboard management consolidated under Settings.

The dashboard currently calculates daily values in the React client using the existing event and observation APIs. This keeps the first analytics layer transparent and easy to extend before prediction endpoints are introduced.
