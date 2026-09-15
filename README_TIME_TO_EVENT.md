# PawPredict Phase 5 — Time-to-Event Challenger

This phase adds an **offline discrete-time survival challenger** for PEE and POOP. It does not change the production model registry, API response, or current 10-minute classifiers.

## Why this exists

The current production models answer: **“Will this happen in the next 10 minutes?”**

The survival challenger asks: **“How long until the next exact pee/poop is likely?”**

A normal regression model is a poor fit because PawPredict has censoring. If tracking stops, sleep begins, or an unobserved period begins before the next exact event, the true event time is unknown. The challenger therefore uses a discrete-time hazard model and censors the example instead of inventing a timestamp.

Observation periods with `peed_during` / `pooped_during` are not treated as exact event times. They remain timing-unknown and the landmark is censored at the start of the observation gap.

## Files

- `backend/app/services/time_to_event.py` — landmark creation, censoring, discrete hazard model, validation metrics, current forecast.
- `backend/scripts/evaluate_time_to_event.py` — offline evaluation CLI.
- `backend/tests/test_time_to_event.py` — core censoring and survival-curve tests.

## Model design

- Targets: `PEE`, `POOP`
- Landmark cadence: every 15 minutes from the existing clean snapshot stream
- Maximum forecast horizon: 120 minutes
- Hazard intervals: 10 minutes
- Covariates: the existing 14 PawPredict behavioral/routine features plus elapsed-time terms
- Estimator: median imputation → standard scaling → logistic discrete-time hazard
- Evaluation: chronological 80/20 split at the landmark level
- Final challenger: refit on all landmarks only after evaluation

No class weighting is used because the conditional hazard probabilities need to retain probabilistic meaning.

## Censoring rules

At each landmark, the endpoint is the earliest of:

1. the next exact target event,
2. the start of sleep,
3. the start of an unobserved period,
4. the 120-minute horizon.

Only #1 is an observed event. #2–#4 are censored outcomes.

## Metrics

- **C-index** — whether shorter predicted times correctly rank earlier observed events. `0.5` is roughly random ordering; higher is better.
- **Mean known Brier** — average time-dependent Brier score using only examples whose event status is actually known at each endpoint. Lower is better.
- **Event MAE** — absolute error in restricted expected event time for exact events in the test period. Lower is better.
- **KM baseline event MAE** — a Kaplan–Meier median-time baseline. The challenger should beat this before promotion is considered.
- **Middle-50% interval coverage** — fraction of exact test events falling inside the model's 25th–75th percentile timing interval when both bounds are estimable.

## Run

From `backend/`:

```bash
python scripts/evaluate_time_to_event.py \
  --dog-id 7ab62dbc-d719-41d4-950c-e5849ae38ccc \
  --timezone America/Chicago
```

Optional machine-readable result:

```bash
python scripts/evaluate_time_to_event.py \
  --dog-id 7ab62dbc-d719-41d4-950c-e5849ae38ccc \
  --timezone America/Chicago \
  --output time_to_event_results/validation.json
```

Tests:

```bash
pytest tests/test_time_to_event.py -q
```

## Promotion gate

Do **not** add these models to production or the registry just because they fit. Phase 5A is model research.

A reasonable next decision is:

- keep a target as research-only if C-index is weak or event MAE does not beat the KM baseline;
- move a target into registry `CANDIDATE` / prospective validation only if chronological evaluation is convincingly better than baseline and forecasts look behaviorally plausible;
- shadow it later before it can affect the product.

This keeps the same evidence-first deployment discipline used for Poop V2.
