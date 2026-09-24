# PawPredict Architecture

```text
React + TypeScript (Vercel)
          |
          | Supabase Auth + REST / JSON
          v
FastAPI (Render)
          | verifies token + dog ownership
          |
          +--------------------+
          |                    |
          v                    v
Supabase PostgreSQL      Potty prediction service
(events, observations,   (feature snapshots,
preferences, calendar)    logistic regression,
                          empirical fallback,
                          holdout metrics)
```

## Data domains

- **Events**: exact timestamped observations such as pee, poop, sleep start/end, treat, zoomies, bath, or vet visit.
- **Observation periods**: time ranges when direct observation was unavailable. Interval-only pee/poop evidence remains interval evidence and does not become a fake event.
- **Scheduled items**: future/planned care items. They are intentionally separate from completed historical events.
- **Preferences**: per-dog event, stat, chart, and UI configuration.

## Prediction flow

1. FastAPI reads up to 60 days of exact events and observation periods.
2. Sleep START/END logs are paired into intervals, including sessions that cross midnight.
3. Five-minute candidate snapshots are generated.
4. Any snapshot whose next 10 minutes overlaps sleep or unobserved time is excluded from model training.
5. Features are created using only information available at the snapshot timestamp.
6. Chronological 80/20 evaluation is calculated.
7. Final logistic-regression models fit all usable history for live inference.
8. If a target lacks enough positive/negative windows, a personalized empirical fallback is used and labeled accordingly.
9. The Today UI requests live probabilities; Insights displays model-quality metrics.


## Multi-user boundary

Each `dogs` row is owned by one Supabase `auth.users` UUID. Every dog-scoped API route validates that ownership before querying or mutating the requested resource. Supabase RLS policies mirror the same boundary as defense in depth.

```text
auth.users
    1
    |
    *
dogs
    1
    |
    +--* events
    +--* observation_periods
    +--* scheduled_items
    +--* preferences
    +--* model_versions / model_predictions / monitoring
```

The backend uses a trusted server-side PostgreSQL connection; browser clients never receive database credentials.

## Session tracking

Nap, nighttime sleep, and walk duration are represented by exact START/END events rather than client-only timers. The frontend reconstructs active state from persisted event history, so navigation or browser reloads do not lose the session.

## Historical corrections

Today and Calendar share the same event editor. Editing an old `event_time` updates the canonical event row, its `updated_at` timestamp, and therefore the prediction service's data fingerprint/cache invalidation path.
