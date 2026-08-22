# PawPredict Architecture

```text
React + TypeScript (Vercel)
          |
          | REST / JSON
          v
FastAPI (Render)
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
