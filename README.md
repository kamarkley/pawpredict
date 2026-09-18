# PawPredict

PawPredict is a personalized, multi-user canine routine tracker and machine-learning application that began with one dog's real behavior history and now supports account-scoped dog profiles. It combines fast mobile event logging, observation-aware data quality, calendar/history views, customizable analytics, and a live model that estimates the chance of a potty event in the next 10 minutes.

## What it does

### Today
- Quick-log configurable events such as pee, poop, potty attempts, treats, zoomies, baths, and care events.
- Start/end persistent Nap, Sleep, and Walk sessions whose timers survive navigation and reloads.
- Expand event details directly beneath the selected quick-log button.
- Track unobserved periods separately from events, including interval-only evidence that a pee or poop happened while the exact time is unknown.
- Show a live **PawPredict AI** card with:
  - any-potty probability in the next 10 minutes,
  - separate pee and poop probabilities,
  - next-hour risk forecast,
  - time since the latest pee, poop, and wake-up,
  - model/estimate confidence,
  - interpretable current drivers.

### Calendar
- Browse all historical tracking dates.
- Open any historical event to correct its date/time or details, or delete an erroneous log.
- See care/appointment markers without cluttering the calendar with every event.
- Schedule vet, grooming, bath, medication, daycare, training, or custom items.
- Tap a date to reveal that day's activity plus a full embedded daily Insights view.

### Insights
- Today, 7-day, 30-day, all-time, and custom ranges.
- Range-aware labels and comparisons.
- Cross-midnight sleep/session accounting.
- Potty timing, outcomes, accidents, sleep, activity, behavior, symptom, and walk charts.
- Observation coverage and interval-potty evidence metrics.
- A model report with chronological holdout PR-AUC, ROC-AUC, Brier score, positive windows, training volume, and strongest learned signals.

### Accounts + dogs
- Sign up/sign in with Supabase Auth.
- Keep each account's dogs and tracking data isolated.
- Create and switch between multiple dog profiles.
- New dogs begin in Learning mode until enough personalized history exists.

### Settings
- Edit the dog profile.
- Enable/disable event types.
- Manage saved logging options.
- Choose/reorder Insight stat cards and charts.
- Customize the app accent color.
- Download a portable JSON backup of the complete PawPredict history.

## Machine learning

The production target is:

> **Will an exact pee or poop event occur in the next 10 minutes?**

PawPredict creates five-minute historical snapshots and trains personalized logistic-regression models for:

1. any potty in the next 10 minutes,
2. pee in the next 10 minutes,
3. poop in the next 10 minutes.

Feature engineering includes elapsed time since the latest pee, poop, potty attempt, and wake-up; same-day potty counts; recent treats/zoomies/potty attempts; cyclical time-of-day and weekday features; and age.

Training windows that overlap logged **unobserved time or sleep are excluded** from negative examples. Pee/poop evidence recorded only at the observation-period level is preserved for data-quality reporting but is never assigned a fabricated timestamp.

When there are not yet enough clean positive windows for a fitted model, the app labels its output **Early personalized estimate** and uses the dog's own empirical timing patterns. Once the minimum data threshold is met, it automatically switches to the fitted personalized model.

See [`ml/MODEL_CARD.md`](ml/MODEL_CARD.md) for modeling assumptions and evaluation details.

## Stack

**Frontend**
- React 19
- TypeScript
- Vite
- Recharts
- Responsive custom CSS

**Backend**
- FastAPI
- SQLAlchemy
- PostgreSQL / Supabase
- Pydantic

**Machine learning**
- Python
- NumPy
- scikit-learn
- Logistic regression baseline with chronological holdout evaluation

**Deployment**
- Vercel frontend
- Render backend
- Supabase Postgres

## Repository layout

```text
backend/       FastAPI API, database models, prediction service
frontend/      React + TypeScript application
database/      SQL migrations and schema references
ml/            Modeling documentation and offline experimentation utilities
docs/          Database/project documentation
tests/         Project tests
```

## Local development

Backend:

```bash
cd backend
source ../.venv/bin/activate
pip install -r requirements.txt
python -m fastapi dev app/main.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Current status

**Phase 7/8 productization release.** Core tracking, historical editing, persistent activity sessions, multi-user authentication, per-account dog ownership, onboarding, RLS, production request instrumentation, and the validated ML lifecycle are implemented. Durable paid background-job infrastructure remains intentionally deferred. See [`README_PRODUCTIZATION_PHASE78.md`](README_PRODUCTIZATION_PHASE78.md) for migration and deployment instructions.
