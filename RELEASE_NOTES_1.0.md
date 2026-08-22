# PawPredict 1.0 — Completion Release

## Added
- Live next-10-minute potty prediction card on Today.
- Separate any-potty, pee, and poop probabilities.
- Personalized logistic-regression training from the live database.
- Early empirical fallback when fitted-model requirements are not yet met.
- Next-hour risk forecast and interpretable prediction drivers.
- Model-quality panel in Insights with PR-AUC, ROC-AUC, Brier score, prevalence, and sample counts.
- Full historical daily Insights inside Calendar after a date is selected.
- Complete JSON data backup from Settings.
- Production model card and updated architecture documentation.

## Improved
- Insight labels adapt to multi-day ranges.
- Multi-day “time since last” cards become average time-between-event statistics.
- Potty timing highlights use peak hourly windows rather than a misleading single circular average.
- Final responsive styling and prediction-focused visual hierarchy.
- SQLAlchemy integrity-error handling import cleanup.

## Modeling safeguards
- No fake timestamps for pee/poop known only within an unobserved interval.
- Negative training snapshots are removed if the outcome window overlaps unobserved time or sleep.
- Nap prediction is intentionally excluded.
- Predictions clearly distinguish fitted ML from an early estimate.
