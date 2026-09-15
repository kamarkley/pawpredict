#!/usr/bin/env python3
"""Evaluate frozen PawPredict survival challengers on strictly future data."""
from __future__ import annotations

import argparse
import csv
import hashlib
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
from app.services.time_to_event_prospective import (  # noqa: E402
    evaluate_frozen_candidate,
    load_frozen_bundle,
)


def fmt(value, digits=3):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="time_to_event_prospective/frozen_challengers.pkl",
    )
    parser.add_argument("--bootstrap", type=int, default=500)
    parser.add_argument("--output-dir", default="time_to_event_prospective")
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    manifest_path = artifact_path.with_suffix(artifact_path.suffix + ".manifest.json")
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing freeze manifest: {manifest_path}. "
            "Prospective evaluation requires the original artifact manifest."
        )
    manifest = json.loads(manifest_path.read_text())
    actual_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    expected_sha256 = manifest.get("sha256")
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "Frozen artifact checksum does not match its manifest. "
            "Do not evaluate a modified/refit artifact as prospective evidence."
        )
    frozen = load_frozen_bundle(artifact_path)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    dog_id = uuid.UUID(frozen.dog_id)
    with SessionLocal() as db:
        bundle = get_training_bundle(db, dog_id, frozen.timezone_name)
        results = [
            evaluate_frozen_candidate(
                frozen,
                frozen.candidates[target],
                bundle,
                bootstrap_replicates=args.bootstrap,
            )
            for target in ("PEE", "POOP")
        ]

    print("=" * 142)
    print("PawPredict Phase 5C — frozen prospective survival validation")
    print("=" * 142)
    print(f"Frozen: {frozen.frozen_at.isoformat()}   Evaluated: {bundle.generated_at.isoformat()}")
    print(
        f"{'TARGET':<6} {'CANDIDATE':<24} {'DAYS':>5} {'LAND':>6} {'EVENT':>6} "
        f"{'C-INDEX':>8} {'BRIER':>8} {'MAE':>8} {'KM MAE':>8} {'IMPROVE':>8} {'P>0':>7} {'P>C50':>7} {'DECISION':<16}"
    )
    print("-" * 142)
    for r in results:
        print(
            f"{r.target:<6} {r.candidate_label:<24} {r.future_days:>5} {r.future_landmarks:>6} {r.future_events:>6} "
            f"{fmt(r.concordance_index):>8} {fmt(r.mean_known_brier):>8} "
            f"{fmt(r.event_mae_minutes,1):>8} {fmt(r.km_baseline_event_mae_minutes,1):>8} "
            f"{(fmt(r.mae_improvement_pct,1)+'%') if r.mae_improvement_pct is not None else '-':>8} "
            f"{fmt(r.bootstrap_p_improvement_positive):>7} {fmt(r.bootstrap_p_cindex_above_half):>7} {r.decision:<16}"
        )
        print(f"        {r.decision_reason}")
        if r.improvement_ci_low is not None:
            print(
                f"        bootstrap 95%: improvement [{r.improvement_ci_low:.1f}%, {r.improvement_ci_high:.1f}%], "
                f"C-index [{r.cindex_ci_low:.3f}, {r.cindex_ci_high:.3f}]"
            )
        print(
            f"        interval coverage: 50%={fmt(r.middle_50_interval_coverage)} "
            f"75%={fmt(r.middle_75_interval_coverage)}"
        )

    payload = {
        "artifact": str(artifact_path.resolve()),
        "artifact_sha256": actual_sha256,
        "frozen_at": frozen.frozen_at.isoformat(),
        "evaluated_at": bundle.generated_at.isoformat(),
        "results": [asdict(r) for r in results],
    }
    (out / "prospective_latest.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n"
    )

    with (out / "prospective_latest.csv").open("w", newline="") as handle:
        fields = [
            "target","candidate_label","frozen_at","evaluated_at","future_days",
            "future_landmarks","future_events","concordance_index","mean_known_brier",
            "event_mae_minutes","km_baseline_event_mae_minutes","mae_improvement_pct",
            "middle_50_interval_coverage","middle_75_interval_coverage",
            "bootstrap_p_improvement_positive","bootstrap_p_cindex_above_half",
            "improvement_ci_low","improvement_ci_high","cindex_ci_low","cindex_ci_high",
            "decision","decision_reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row.pop("calibration", None)
            writer.writerow(row)

    with (out / "prospective_calibration.csv").open("w", newline="") as handle:
        fields = [
            "target","candidate_label","endpoint_minutes","n_known",
            "predicted_rate","observed_rate","absolute_gap",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in results:
            for point in r.calibration:
                row = asdict(point)
                row.update({"target": r.target, "candidate_label": r.candidate_label})
                writer.writerow(row)

    print("=" * 142)
    print(f"Saved prospective outputs to: {out.resolve()}")
    print("WAIT is expected immediately after freezing. Never refit the frozen artifact during this test.")


if __name__ == "__main__":
    main()
