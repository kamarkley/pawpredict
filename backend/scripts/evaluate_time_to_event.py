#!/usr/bin/env python3
"""Evaluate PawPredict's experimental time-to-event challengers."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Intentional model registration for standalone SQLAlchemy scripts.
from app.models.dog import Dog  # noqa: F401,E402
from app.database import SessionLocal  # noqa: E402
from app.services.potty_prediction import get_training_bundle  # noqa: E402
from app.services.time_to_event import (  # noqa: E402
    fit_survival_challenger,
    predict_time_to_event,
)


def _fmt(value, digits=3):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dog-id", required=True)
    parser.add_argument("--timezone", default="America/Chicago")
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    with SessionLocal() as db:
        dog_id = uuid.UUID(args.dog_id)
        bundle = get_training_bundle(db, dog_id, args.timezone)
        results = []
        print("=" * 118)
        print("PawPredict Phase 5 — discrete-time survival challenger")
        print("=" * 118)
        print(
            f"{'TARGET':<7} {'FIT':<5} {'LAND':>6} {'EVENT':>6} {'TEST':>6} "
            f"{'C-INDEX':>8} {'BRIER':>8} {'MAE':>8} {'KM MAE':>8} {'50% COV':>8}"
        )
        print("-" * 118)

        for target in ("PEE", "POOP"):
            fitted = fit_survival_challenger(bundle, target)
            forecast = predict_time_to_event(fitted, bundle)
            m = fitted.metrics
            print(
                f"{target:<7} {str(m.fitted):<5} {m.landmarks:>6} {m.events:>6} "
                f"{m.test_landmarks:>6} {_fmt(m.concordance_index):>8} "
                f"{_fmt(m.mean_known_brier):>8} {_fmt(m.event_mae_minutes, 1):>8} "
                f"{_fmt(m.km_baseline_event_mae_minutes, 1):>8} "
                f"{_fmt(m.middle_50_interval_coverage):>8}"
            )
            if forecast is not None:
                interval = (
                    f"{int(forecast.p25_minutes)}–{int(forecast.p75_minutes)} min"
                    if forecast.p25_minutes is not None and forecast.p75_minutes is not None
                    else "not yet bounded"
                )
                median = (
                    f"{int(forecast.median_minutes)} min"
                    if forecast.median_minutes is not None
                    else ">120 min / no median inside horizon"
                )
                print(
                    f"        now: P30={forecast.probability_30m:.1%} "
                    f"P60={forecast.probability_60m:.1%} "
                    f"P120={forecast.probability_120m:.1%} "
                    f"expected≈{forecast.expected_minutes:.0f} min "
                    f"median={median} middle50={interval}"
                )
            else:
                print("        now: forecast unavailable (not fitted, sleeping, or unobserved)")

            results.append(
                {
                    "metrics": asdict(m),
                    "current_forecast": asdict(forecast) if forecast is not None else None,
                }
            )

        print("=" * 118)
        print("This is an offline challenger only. It does not change production inference or the model registry.")
        print("Compare event MAE with KM MAE; lower is better. C-index > 0.5 indicates useful ordering.")

        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(results, indent=2, default=str) + "\n")
            print(f"Saved: {path}")


if __name__ == "__main__":
    main()
