# PawPredict ML workspace

The first modeling target is **potty in the next 10 minutes**. The goal is a personalized probability model, not a generic puppy rule engine.

## Initial target
At each eligible observed timestamp:

- `target_10m = 1` when a PEE or POOP occurs in the following 10 minutes.
- `target_10m = 0` when the following 10 minutes are directly observed and no potty occurs.
- Windows that overlap unobserved time are excluded from the negative class.
- Observation-period potty outcomes are retained as interval evidence but are **not assigned fake event times**.

## Baseline feature set
- minutes since last pee / poop / potty attempt
- minutes since last nap end / nighttime wake
- minutes awake (when directly inferable)
- pee and poop counts so far that day
- hour-of-day cyclical features
- puppy age in days
- recent treat / zoomies indicators
- previous potty outcome/location
- observed coverage in recent windows

## Models
1. Logistic regression baseline (interpretable).
2. Gradient boosted trees once enough positive examples exist.
3. Calibration evaluation before showing probabilities in-app.

Do not use nap-onset or nap-duration prediction: naps are partly owner-directed, so those targets would learn the owner's kennel choices rather than Maverick's natural behavior.
