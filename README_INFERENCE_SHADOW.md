# PawPredict Phase 2 + 3
## Registry-Driven Inference + Champion/Challenger Shadow Deployment

This patch connects the Phase 1 model registry to live inference and adds a
prospective prediction ledger for silent challenger scoring.

It is intentionally rolled out in gates even though the code is installed at once.

---

# Architecture

```text
GET /dogs/{dog}/predictions/potty
                 |
                 v
        Model Registry
                 |
      +----------+----------+
      |                     |
      v                     v
PRODUCTION champion       SHADOW challenger(s)
      |                     |
      |                 scored silently
      |                     |
      v                     v
user response          model_predictions
      |                     |
      +---------------------+
                 |
        after 10 min horizon
                 |
                 v
         outcome resolver
                 |
       RESOLVED / INELIGIBLE
```

The champion path is computed **before** any shadow/telemetry work. The ledger,
outcome resolver, and challengers run as a FastAPI background task with their
own database session, so shadow scoring does not sit on the user-facing latency
path.

If the shadow system throws an exception, the user still receives the champion
prediction.

---

# Files

Copy/replace these files in PawPredict:

```text
backend/app/models/model_prediction.py              NEW
backend/app/services/potty_prediction.py            REPLACE
backend/app/services/prediction_ledger.py            NEW
backend/app/routes/predictions.py                   REPLACE
backend/scripts/inspect_model_runtime.py             NEW
backend/scripts/start_shadow_model.py                NEW
backend/scripts/resolve_model_prediction_outcomes.py NEW
database/migrations/008_model_prediction_ledger.sql NEW
```

---

# Step 1 — copy files

Replace the existing:

```text
backend/app/services/potty_prediction.py
backend/app/routes/predictions.py
```

with the versions in this package.

Add all other files.

Do **not** delete Phase 1 registry files.

---

# Step 2 — make SQLAlchemy aware of the new model

Where PawPredict imports ORM models at application startup, add:

```python
from app.models.model_prediction import ModelPrediction  # noqa: F401
```

If the app does not have a central model-import file, this is not required for
ordinary ORM queries because the service imports the class directly. It is still
good practice if you maintain a central model registry.

---

# Step 3 — run migration 008 in Supabase

Run:

```text
database/migrations/008_model_prediction_ledger.sql
```

This creates:

```text
model_predictions
vw_model_prediction_monitoring
vw_model_prediction_daily
```

The table stores exact champion/shadow version, probability, feature context,
and delayed outcome.

Predictions are deduplicated into one row per model/target/role per 5-minute
bucket so frontend polling does not flood the database.

---

# Step 4 — verify registry-driven champion inference BEFORE any shadow model

From `backend/`:

```bash
source ../.venv/bin/activate

python scripts/inspect_model_runtime.py \
  --timezone America/Chicago
```

Expected:

```text
ANY  -> v1-any-full-60d
PEE  -> v1-pee-full-60d
POOP -> v1-poop-full-60d
```

Every line should say:

```text
source=REGISTRY
```

If any says `LEGACY_FALLBACK`, stop before moving forward and inspect the
corresponding model registry row.

At this stage all three production configurations are the same recipes that
were already live, so the UI should behave normally.

---

# Step 5 — run PawPredict locally

Start the backend/frontend normally.

Open the Today page several times.

Confirm:

- predictions load
- no 500 response
- Any/Pee/Poop probabilities look normal
- forecast renders
- model report renders

Then query Supabase:

```sql
select
    target,
    role,
    version_label,
    outcome_status,
    probability,
    prediction_time
from vw_model_prediction_monitoring
order by prediction_time desc
limit 20;
```

You should initially see three `CHAMPION` rows per 5-minute bucket.

No SHADOW rows yet. That is expected.

---

# Step 6 — activate Poop V2 as a silent shadow

First get Maverick's UUID:

```sql
select id, name from dogs;
```

Then:

```bash
python scripts/start_shadow_model.py \
  --dog-id YOUR_DOG_UUID \
  --target POOP \
  --version-label v2-poop-lean-30d \
  --reason "Validated Poop V2 entering silent production shadow."
```

Check:

```sql
select target, version_label, status
from model_versions
order by target, version_label;
```

Expected Poop:

```text
v1-poop-full-60d    PRODUCTION
v2-poop-lean-30d    SHADOW
```

The app STILL serves V1 Poop.

---

# Step 7 — hit the prediction endpoint again

Open/refresh the Today page.

Then:

```sql
select
    target,
    role,
    version_label,
    probability,
    outcome_status,
    prediction_time
from vw_model_prediction_monitoring
order by prediction_time desc
limit 30;
```

You should now see, in each new prediction bucket:

```text
ANY   CHAMPION  v1-any-full-60d
PEE   CHAMPION  v1-pee-full-60d
POOP  CHAMPION  v1-poop-full-60d
POOP  SHADOW    v2-poop-lean-30d
```

The shadow probability never enters the API response.

---

# Step 8 — outcome resolution

The prediction route automatically resolves old PENDING rows whenever PawPredict
is used again.

You can also resolve manually:

```bash
python scripts/resolve_model_prediction_outcomes.py \
  --timezone America/Chicago
```

After 10+ minutes, check:

```sql
select
    target,
    role,
    version_label,
    probability,
    observed_outcome,
    outcome_status,
    ineligible_reason
from vw_model_prediction_monitoring
order by prediction_time desc
limit 30;
```

Valid observed windows become:

```text
RESOLVED
```

Windows later found to overlap sleep or an unobserved period become:

```text
INELIGIBLE
```

They should never be treated as negatives.

---

# Step 9 — parity gate

Before promoting Poop V2:

1. Registry runtime says V1 for all three champions.
2. Today page works normally.
3. Champion rows are logging.
4. Poop V2 SHADOW rows log without changing UI.
5. Matured predictions resolve correctly.
6. A shadow failure does not cause the endpoint to fail.

Because Poop V2 already passed the frozen prospective validation, this shadow
gate is primarily an infrastructure/parity test rather than another long
model-selection period.

A handful of normal app interactions is enough to verify the plumbing.

---

# Step 10 — promote Poop V2

Use the Phase 1 promotion script:

```bash
python scripts/promote_model.py \
  --dog-id YOUR_DOG_UUID \
  --target POOP \
  --version-label v2-poop-lean-30d \
  --reason "Promoted after prospective validation and successful silent shadow integration."
```

The registry transaction changes:

```text
v1-poop-full-60d    PRODUCTION -> RETIRED
v2-poop-lean-30d    SHADOW     -> PRODUCTION
```

The next prediction request invalidates the runtime cache because registry
`updated_at` changed.

No hard-coded inference edit is required.

That is the point of the registry control plane.

---

# Production configuration after promotion

```text
ANY
  v1-any-full-60d
  60 days
  14 features
  raw
  PRODUCTION

PEE
  v1-pee-full-60d
  60 days
  14 features
  raw
  PRODUCTION

POOP
  v2-poop-lean-30d
  30 days
  4 features:
    minutes_since_poop
    poop_count_today
    hour_sin
    hour_cos
  raw
  PRODUCTION
```

---

# What makes this different from the old pipeline

Previously:

```text
Python code decided model behavior.
```

Now:

```text
registry decides model behavior
       +
code executes the registered configuration.
```

That means a future model promotion can change training window/features/calibration
without editing the prediction endpoint.

---

# Prediction ledger semantics

`model_predictions` deliberately separates model scoring from truth.

At prediction time:

```text
outcome_status = PENDING
```

After the horizon closes:

```text
observed + eligible      -> RESOLVED, outcome 0/1
unobserved overlap       -> INELIGIBLE
sleep overlap            -> INELIGIBLE
```

This avoids silently turning unknown behavior into negative labels.

---

# Power BI later

The migration creates:

```text
vw_model_prediction_monitoring
vw_model_prediction_daily
```

The daily view already contains:

- model version
- target
- champion/shadow role
- prediction count
- resolved count
- ineligible count
- average probability
- observed positive rate
- Brier score

This will become the first real fact table for the PawPredict ML Operations
Power BI dashboard.

---

# Commit

Once the parity/shadow tests work:

```bash
git add \
  backend/app/models/model_prediction.py \
  backend/app/services/potty_prediction.py \
  backend/app/services/prediction_ledger.py \
  backend/app/routes/predictions.py \
  backend/scripts/inspect_model_runtime.py \
  backend/scripts/start_shadow_model.py \
  backend/scripts/resolve_model_prediction_outcomes.py \
  database/migrations/008_model_prediction_ledger.sql

git commit -m "Add registry-driven inference and shadow model scoring"

git push origin main
```

Do not commit runtime output folders or local experiment ZIPs.
