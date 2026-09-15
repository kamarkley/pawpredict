# PawPredict Phase 4 — Production ML Monitoring + Drift Detection

This phase turns the existing immutable prediction ledger into a production monitoring layer. It does **not** backfill fake live predictions. Monitoring starts from the predictions that were actually emitted by registered champion/shadow models.

## What gets monitored

For every `PRODUCTION` and `SHADOW` model version, the batch job computes rolling 7-day, 14-day, and 30-day snapshots.

Performance/data-quality metrics:

- prediction count
- resolved / ineligible / pending counts
- observed coverage
- positive count and observed prevalence
- mean predicted probability
- Brier score
- Expected Calibration Error (ECE)
- calibration gap
- comparison with the immediately preceding equal-length window

Drift metrics:

- prediction-distribution PSI
- per-feature PSI from `model_predictions.feature_snapshot`
- recent/reference feature mean and standard deviation

Status dimensions:

- `performance_status`
- `drift_status`
- overall `health_status`

Allowed values:

- `HEALTHY`
- `WATCH`
- `DEGRADED`
- `INSUFFICIENT_DATA`

`INSUFFICIENT_DATA` is expected at first. The production ledger only began collecting predictions recently, so PawPredict should not pretend it has a historical live baseline that does not exist.

## Files

- `database/migrations/009_model_monitoring.sql`
- `backend/app/services/model_monitoring.py`
- `backend/scripts/run_model_monitoring.py`
- `backend/scripts/inspect_model_monitoring.py`
- `backend/tests/test_model_monitoring_metrics.py`

## Database objects

### `model_monitoring_snapshots`

One persisted daily snapshot per model version / date / rolling window. Rerunning the job on the same UTC date updates that snapshot instead of duplicating it.

### `model_feature_drift`

Per-feature live drift measurements linked to a monitoring snapshot.

### Reporting views

- `vw_model_monitoring_history`
- `vw_model_monitoring_latest`
- `vw_model_feature_drift_history`
- `vw_model_feature_drift_latest`

These are intentionally shaped for the future Power BI ML Ops dashboard.

## Reference-window design

For a 7-day snapshot:

- recent = last 7 days
- reference = the 7 days immediately before that

For 14-day and 30-day snapshots, the same equal-length preceding-window rule is used.

This is a live-to-live comparison. It answers: **has the model/input distribution changed compared with its immediately preceding production period?**

## Thresholds

Defaults are defined in `MonitoringThresholds`.

Data sufficiency:

- performance: >= 100 resolved predictions and >= 5 positives
- drift: >= 200 predictions in both recent and reference windows
- feature drift: >= 100 non-null values in each window

PSI:

- `< 0.10` healthy
- `0.10–0.25` watch
- `>= 0.25` degraded

Calibration:

- ECE `>= 0.06` watch
- ECE `>= 0.10` degraded
- absolute calibration gap `>= 0.05` watch
- absolute calibration gap `>= 0.10` degraded

Coverage:

- `< 70%` watch
- `< 50%` degraded

Brier degradation is evaluated against the preceding window when both windows have enough resolved outcomes. The code requires both a relative and meaningful absolute deterioration before marking a Brier change as degraded.

These are operational guardrails, not claims about universal statistical cutoffs. They live in one dataclass so they can be tuned later from real PawPredict telemetry.

## Installation / first run

### 1. Add the files

Merge this package into the PawPredict repo, preserving paths.

### 2. Run migration 009 in Supabase

Run:

`database/migrations/009_model_monitoring.sql`

### 3. Resolve old enough outcomes first

From `backend/`:

```bash
python scripts/resolve_model_prediction_outcomes.py --timezone America/Chicago
```

### 4. Run monitoring for Maverick

```bash
python scripts/run_model_monitoring.py \
  --dog-id 7ab62dbc-d719-41d4-950c-e5849ae38ccc
```

The first result will probably be mostly `INSUFFICIENT_DATA`. That is correct because the production ledger has only recently started accumulating live predictions.

### 5. Inspect the latest 7-day snapshot

```bash
python scripts/inspect_model_monitoring.py \
  --dog-id 7ab62dbc-d719-41d4-950c-e5849ae38ccc \
  --window 7
```

### 6. Supabase sanity query

```sql
select
    target,
    version_label,
    lifecycle_status,
    window_days,
    prediction_count,
    resolved_count,
    positive_count,
    coverage_rate,
    brier_score,
    ece,
    prediction_psi,
    max_feature_psi,
    performance_status,
    drift_status,
    health_status,
    as_of_time
from vw_model_monitoring_latest
order by target, window_days;
```

### 7. Feature-drift sanity query

```sql
select
    target,
    version_label,
    window_days,
    feature_name,
    recent_count,
    reference_count,
    recent_mean,
    reference_mean,
    psi,
    drift_status
from vw_model_feature_drift_latest
order by target, window_days, psi desc nulls last;
```

## Tests

From `backend/`:

```bash
pytest tests/test_model_monitoring_metrics.py -q
```

If `pytest` is not already in the environment, do not install it just to complete the migration. The production smoke test is the monitoring CLI plus the Supabase views; tests can be added to the development dependency set when CI is formalized.

## Daily scheduling later

Do **not** put this work in the prediction request path. It is a batch monitoring job. Once the manual run is verified, schedule this sequence daily in a worker/cron environment:

1. resolve closed prediction outcomes
2. run model monitoring
3. later: evaluate alert transitions / send notifications

FastAPI `BackgroundTasks` remains appropriate for low-risk prediction telemetry, but monitoring should be a durable scheduled job rather than request-bound work.

## Power BI surfaces created by this phase

The views now support four future report pages without reshaping raw JSON in Power BI:

- **Model Fleet** — version, lifecycle state, current health
- **Performance & Calibration** — Brier, ECE, prevalence, coverage over time
- **Drift & Data Quality** — prediction PSI and feature PSI
- **Deployment History** — combine monitoring views with the registry event/evaluation views from Phase 1

## Git commit

After the migration and smoke test succeed:

```bash
git add \
  backend/app/services/model_monitoring.py \
  backend/scripts/run_model_monitoring.py \
  backend/scripts/inspect_model_monitoring.py \
  backend/tests/test_model_monitoring_metrics.py \
  database/migrations/009_model_monitoring.sql \
  README_MODEL_MONITORING.md

git commit -m "Add production model monitoring and drift detection"
git push origin main
```
