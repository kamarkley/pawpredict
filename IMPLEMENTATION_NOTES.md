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
