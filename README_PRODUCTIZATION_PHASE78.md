# PawPredict Phase 7/8 — Multi-user productization + production hardening

This release turns the original single-dog PawPredict proof-of-concept into a multi-user application architecture while preserving the validated ML stack.

## What changed

### Product / UX
- Email/password authentication through Supabase Auth.
- Multiple dogs per account with an active-dog selector.
- New-dog onboarding and automatic per-dog defaults.
- Historical event editing from Calendar, including correcting the **date and time** of an old log.
- Historical event deletion from the same shared editor used on Today.
- Persistent START/END session controls for Nap, Sleep, and Walk. Session timers are reconstructed from stored backend timestamps, so navigation/reload does not reset them.
- New dogs show **Learning mode** until enough personalized history exists for fitted ML models.

### Security / tenancy
- `dogs.owner_user_id` links each dog to `auth.users.id`.
- Every dog-scoped FastAPI route validates ownership before returning or mutating data.
- Bearer tokens are verified against Supabase Auth.
- Supabase Row Level Security policies add defense in depth to dog-owned tables, and reporting views use `security_invoker` so they honor the caller's RLS policies.
- Unauthorized dog IDs return `404` rather than revealing that another user's dog exists.

### Production hardening
- Request IDs and server timing headers.
- Structured request logging.
- Configurable CORS allow-list.
- Lightweight per-instance request rate limit.
- Optional Sentry integration.
- Auth/security unit tests and explicit historical-edit validation tests.
- GitHub Actions CI for backend tests/compile checks and frontend lint/build gates.

## Required migration order

Do **not** run `011_enforce_dog_ownership.sql` before backfilling existing dogs.

### 1. Run migration 010

In Supabase SQL Editor, run:

```text
database/migrations/010_multi_user_auth.sql
```

This adds `dogs.owner_user_id`, creates ownership-aware RLS policies, and intentionally leaves existing dog ownership nullable for the backfill step.

### 2. Create/sign in to the PawPredict account that should own Maverick

Supabase Dashboard → **Authentication → Users** will show the user's UUID after the account exists.

You can inspect it with:

```sql
select id, email, created_at
from auth.users
order by created_at;
```

### 3. Backfill the existing dog

Replace `YOUR-SUPABASE-USER-UUID` below:

```sql
update public.dogs
set owner_user_id = 'YOUR-SUPABASE-USER-UUID'
where id = '7ab62dbc-d719-41d4-950c-e5849ae38ccc';
```

Verify **every** dog has an owner:

```sql
select id, name, owner_user_id
from public.dogs
order by name;

select count(*) as unowned_dogs
from public.dogs
where owner_user_id is null;
```

`unowned_dogs` must be `0` before continuing.

### 4. Run migration 011

```text
database/migrations/011_enforce_dog_ownership.sql
```

The migration refuses to run if any unowned dog remains, then makes `owner_user_id` NOT NULL.

## Supabase Auth setup

Use Supabase Dashboard → **Authentication → Providers → Email**.

Email/password sign-in works with either confirmation mode:
- If email confirmation is disabled, signup returns a session immediately.
- If confirmation is enabled, PawPredict tells the user to confirm their email and then sign in.

For production confirmation links, set the Supabase **Site URL** to the deployed Vercel frontend. Add localhost as an allowed redirect URL for local testing if needed.

The browser uses the Supabase anon/publishable key. **Never put a service-role key or database password in frontend environment variables.**

## Environment variables

### Backend

Copy `backend/.env.example` and configure:

```dotenv
DATABASE_URL=postgresql://...
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_OR_PUBLISHABLE_KEY
CORS_ORIGINS=http://localhost:5173,https://YOUR_VERCEL_DOMAIN
RATE_LIMIT_PER_MINUTE=180
APP_ENV=development
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.05
```

The backend database URL must remain server-side only. The API performs ownership checks even when the trusted PostgreSQL role bypasses RLS; RLS protects direct authenticated reads as an additional layer, while direct authenticated writes are revoked so application validation stays authoritative.

### Frontend

```dotenv
VITE_API_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_OR_PUBLISHABLE_KEY
```

No additional Supabase npm SDK is required in this patch; the small auth client uses Supabase Auth's REST endpoints directly.

## Local verification

Backend:

```bash
cd backend
source ../.venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python -m fastapi dev app/main.py
```

Frontend:

```bash
cd frontend
npm install
npm run lint
npx tsc -b
npm run dev
```

Then verify:
1. Sign in.
2. Maverick appears only for the account that owns him.
3. Calendar → prior date → event → Edit → change date/time → Save.
4. The corrected event disappears from the old day and appears on the new day.
5. Start Nap/Sleep/Walk, reload the browser, and confirm the timer remains active.
6. End the session and verify a matching END log appears.
7. Create a second dog and confirm it receives its own options/preferences and Learning mode.
8. Sign in with a different test account and confirm it cannot access the first account's dog IDs.

## CI / deployment gate

`.github/workflows/ci.yml` runs on pushes to `main` and pull requests. It installs clean Linux dependencies, runs backend tests, compiles backend modules, lints the frontend, and performs a production Vite build. Render/Vercel can continue using their GitHub auto-deploy integrations after CI is green.

## Deployment order

1. Deploy/run migration 010.
2. Configure Supabase Auth and production env vars.
3. Backfill existing dog ownership.
4. Run migration 011.
5. Deploy the backend.
6. Deploy the frontend.
7. Smoke-test sign-in, dog listing, logging, historical editing, predictions, and export.

If the frontend is deployed before the backend/auth environment is ready, all API requests will become authenticated and can fail with `401/503`; deploy the pieces as one coordinated release.

## Security model

PawPredict uses three layers:

```text
Supabase Auth session
        ↓
FastAPI verifies bearer token
        ↓
FastAPI verifies dog ownership
        ↓
PostgreSQL/Supabase RLS (defense in depth)
```

Global configuration tables such as event/stat/chart type definitions are not dog-private. Dog-owned records are tenant-scoped.

## Rate limiting / observability

The included rate limiter is intentionally a **single-instance safety valve**, not a distributed production quota system. If the API scales to multiple Render instances, replace it with Redis or an API-gateway rate limiter.

Sentry is optional. If `SENTRY_DSN` is blank, PawPredict runs normally without it.

## Deferred on purpose

The paid/durable scheduled monitoring worker remains deferred. Phase 4 monitoring can still be run manually. A production queue/worker and scheduled monitoring service should be added when the product warrants the infrastructure cost.

## Rollback notes

- App rollback: redeploy the previous frontend/backend commit.
- Migration 010 should generally **not** be blindly reversed after users begin creating data. Ownership becomes part of the data model.
- If release verification fails before multi-user use begins, leave ownership columns/policies in place and roll back application code while investigating.
- Never remove `owner_user_id` from existing dogs without first preserving the account-to-dog mapping.
