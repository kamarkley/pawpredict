# PawPredict Model Registry — Phase 1

This is the first infrastructure step toward a real champion/challenger ML system.

## What this adds

### `model_versions`
One record per reproducible model configuration:
- target
- version label
- model family
- lifecycle status
- features
- training window
- sample-weight strategy
- calibration method
- training metadata
- code/artifact references
- configuration JSON

Lifecycle states:

```text
CANDIDATE → SHADOW → PRODUCTION → RETIRED
                 ↘ REJECTED
```

PostgreSQL enforces **one production champion per dog + target**.

### `model_evaluations`
Appendable history for:
- validation
- rolling backtests
- historical confirmation
- prospective shadow evaluation
- future production monitoring

This prevents PawPredict from overwriting yesterday's metric with today's metric.

### `model_registry_events`
Append-only audit history for:
- registration
- status changes
- promotion
- retirement/rejection

This answers the production question:

> Why is this model live?

instead of only:

> Which model is live?

---

# Install

## 1. Copy the files

Merge these into the existing PawPredict repo:

```text
backend/app/models/model_version.py
backend/app/models/model_evaluation.py
backend/app/models/model_registry_event.py
backend/app/schemas/model_registry.py
backend/app/services/model_registry.py
backend/app/routes/model_registry.py
backend/scripts/seed_model_registry.py
backend/scripts/promote_model.py
database/migrations/006_model_registry.sql
database/model_registry_seed.json
```

## 2. Run migration 006

Use the same method used for PawPredict migrations 002–005.

Run:

```text
database/migrations/006_model_registry.sql
```

against the Supabase/PostgreSQL database.

Do **not** run the seed script before the migration.

## 3. Seed the V1/V2 history

From `backend/`:

```bash
source ../.venv/bin/activate
python scripts/seed_model_registry.py
```

Because PawPredict currently has one dog, it should select Maverick automatically.

This intentionally creates:

```text
ANY
  v1 full 60d             PRODUCTION
  v2 lean 21d sigmoid     REJECTED

PEE
  v1 full 60d             PRODUCTION
  v2 weighted 14d         REJECTED

POOP
  v1 full 60d             PRODUCTION
  v2 lean 30d             CANDIDATE
```

Poop V2 is **not** marked production yet.

That is deliberate. A registry should describe reality. The live prediction
service still needs to be refactored to execute target-specific registry
configurations before V2 Poop is promoted.

## 4. Load the new ORM models

Where the app currently imports SQLAlchemy models at startup, add:

```python
from app.models.model_version import ModelVersion  # noqa: F401
from app.models.model_evaluation import ModelEvaluation  # noqa: F401
from app.models.model_registry_event import ModelRegistryEvent  # noqa: F401
```

## 5. Optional internal/read-only API

The included `model_registry.py` route is intentionally read-only.

When you are ready to expose it, add:

```python
from app.routes.model_registry import router as model_registry_router
```

and:

```python
app.include_router(model_registry_router)
```

For now, it is reasonable to leave this route unregistered until authentication
exists. The registry itself still works through database/service/scripts.

---

# What comes next

## Phase 2 — connect inference to the registry

Refactor `potty_prediction.py` so each target asks:

```text
What is the production model configuration for this dog + target?
```

rather than all targets sharing the same hard-coded feature list/model.

That will let production become:

```text
ANY  → V1 full-history
PEE  → V1 full-history
POOP → V2 30-day lean model
```

## Phase 3 — champion/challenger shadow inference

For every live prediction:

```text
champion prediction → returned to user
challenger prediction → logged silently
```

The challenger does not influence the app.

Later, once enough true outcomes exist, PawPredict automatically creates a
`PROSPECTIVE_SHADOW` evaluation record.

## Phase 4 — monitoring

Add daily/weekly model-health snapshots:
- PR-AUC
- ROC-AUC
- Brier
- ECE
- prevalence
- prediction distribution
- data coverage
- feature drift
- alert burden
- event capture rate

## Phase 5 — Power BI

Migration 006 creates:

```text
vw_model_registry_overview
vw_model_evaluation_history
```

specifically so your first Power BI dashboard can use clean reporting views.

Suggested dashboard pages:

1. **Model Fleet**
   - production model by target
   - challenger status
   - feature count
   - training window
   - calibration method

2. **Performance**
   - PR-AUC over evaluation windows
   - ROC-AUC
   - Brier
   - ECE
   - baseline prevalence

3. **Deployment Decisions**
   - V1 vs V2
   - prospective result
   - promotion/rejection decision

4. **Product Utility**
   - event capture
   - alerts/day
   - alert precision

That gives you a legitimate Power BI project built around a real ML system.
