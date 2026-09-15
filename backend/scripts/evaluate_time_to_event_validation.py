#!/usr/bin/env python3
"""Run PawPredict Phase 5B multi-horizon rolling survival validation."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.dog import Dog  # noqa: F401,E402
from app.database import SessionLocal  # noqa: E402
from app.services.potty_prediction import get_training_bundle  # noqa: E402
from app.services.time_to_event_validation import (  # noqa: E402
    evaluate_target_grid,
    select_best_candidate,
)


def fmt(v, digits=3):
    if v is None:
        return "-"
    return f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dog-id", required=True)
    parser.add_argument("--timezone", default="America/Chicago")
    parser.add_argument("--output-dir", default="time_to_event_validation")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_results = []
    selected = []
    with SessionLocal() as db:
        bundle = get_training_bundle(db, uuid.UUID(args.dog_id), args.timezone)
        print("=" * 142)
        print("PawPredict Phase 5B — purged rolling multi-horizon survival validation")
        print("=" * 142)
        print(
            f"{'TARGET':<6} {'HORIZON':>7} {'FEATURES':<9} {'FOLDS':>5} {'TEST':>6} {'EVENT':>6} "
            f"{'C-INDEX':>8} {'BRIER':>8} {'MAE':>8} {'KM MAE':>8} {'IMPROVE':>8} {'50%COV':>7} {'75%COV':>7} {'DECISION':<12}"
        )
        print("-" * 142)

        for target in ("PEE", "POOP"):
            results = evaluate_target_grid(bundle, target)
            all_results.extend(results)
            for result in results:
                s = result.summary
                print(
                    f"{target:<6} {s.spec.horizon_minutes:>6}m {s.spec.feature_set:<9} {s.fitted_folds:>5} "
                    f"{s.test_landmarks:>6} {s.test_events:>6} {fmt(s.concordance_index):>8} "
                    f"{fmt(s.mean_known_brier):>8} {fmt(s.event_mae_minutes,1):>8} "
                    f"{fmt(s.km_baseline_event_mae_minutes,1):>8} "
                    f"{(fmt(s.mae_improvement_pct,1)+'%') if s.mae_improvement_pct is not None else '-':>8} "
                    f"{fmt(s.middle_50_interval_coverage):>7} {fmt(s.middle_75_interval_coverage):>7} {s.decision:<12}"
                )
            best = select_best_candidate([r.summary for r in results])
            selected.append(best)
            if best is None:
                print(f"  -> {target}: no candidate cleared the evidence gate.")
            else:
                print(
                    f"  -> {target}: best evidence = {best.spec.label}; "
                    f"C-index {fmt(best.concordance_index)}, MAE {fmt(best.event_mae_minutes,1)} min, "
                    f"KM {fmt(best.km_baseline_event_mae_minutes,1)} min, improvement {fmt(best.mae_improvement_pct,1)}%."
                )
            print()

    summaries = [asdict(r.summary) for r in all_results]
    (out / "summary.json").write_text(json.dumps({"candidates": summaries, "selected": [asdict(x) if x else None for x in selected]}, indent=2, default=str) + "\n")

    with (out / "summary.csv").open("w", newline="") as f:
        fields = ["target","horizon_minutes","feature_set","fitted_folds","test_landmarks","test_events","concordance_index","mean_known_brier","event_mae_minutes","km_baseline_event_mae_minutes","mae_improvement_pct","middle_50_interval_coverage","middle_75_interval_coverage","decision"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in all_results:
            s = r.summary
            w.writerow({
                "target": s.spec.target, "horizon_minutes": s.spec.horizon_minutes, "feature_set": s.spec.feature_set,
                "fitted_folds": s.fitted_folds, "test_landmarks": s.test_landmarks, "test_events": s.test_events,
                "concordance_index": s.concordance_index, "mean_known_brier": s.mean_known_brier,
                "event_mae_minutes": s.event_mae_minutes, "km_baseline_event_mae_minutes": s.km_baseline_event_mae_minutes,
                "mae_improvement_pct": s.mae_improvement_pct, "middle_50_interval_coverage": s.middle_50_interval_coverage,
                "middle_75_interval_coverage": s.middle_75_interval_coverage, "decision": s.decision,
            })

    with (out / "folds.csv").open("w", newline="") as f:
        fields = ["target","horizon_minutes","feature_set","fold","train_landmarks","train_events","test_landmarks","test_events","concordance_index","mean_known_brier","event_mae_minutes","km_baseline_event_mae_minutes","middle_50_interval_coverage","middle_75_interval_coverage"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in all_results:
            for m in r.summary.fold_metrics:
                row = asdict(m); row.update({"target":r.summary.spec.target,"horizon_minutes":r.summary.spec.horizon_minutes,"feature_set":r.summary.spec.feature_set}); w.writerow(row)

    with (out / "calibration.csv").open("w", newline="") as f:
        fields = ["target","horizon_minutes","feature_set","endpoint_minutes","n_known","predicted_rate","observed_rate","absolute_gap"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in all_results:
            for p in r.summary.calibration:
                row = asdict(p); row.update({"target":r.summary.spec.target,"horizon_minutes":r.summary.spec.horizon_minutes,"feature_set":r.summary.spec.feature_set}); w.writerow(row)

    print("=" * 142)
    print(f"Saved validation artifacts to: {out.resolve()}")
    print("PROMISING is a research gate only; it does not promote anything to production.")


if __name__ == "__main__":
    main()
