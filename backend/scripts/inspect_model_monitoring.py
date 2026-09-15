from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text

from app.database import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect latest PawPredict model-health snapshots.")
    parser.add_argument("--dog-id", default=None, help="Optional dog UUID.")
    parser.add_argument("--window", type=int, default=7, help="Monitoring window in days. Default: 7.")
    args = parser.parse_args()

    sql = """
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
            health_reasons,
            as_of_time
        from vw_model_monitoring_latest
        where window_days = :window_days
    """
    params = {"window_days": args.window}
    if args.dog_id:
        sql += " and dog_id = :dog_id"
        params["dog_id"] = args.dog_id
    sql += " order by target, lifecycle_status desc, version_label"

    with SessionLocal() as db:
        rows = db.execute(text(sql), params).mappings().all()

    if not rows:
        print("No monitoring snapshots found. Run scripts/run_model_monitoring.py first.")
        return

    print("=" * 110)
    print(f"Latest PawPredict monitoring — {args.window}d window")
    print("=" * 110)
    for row in rows:
        coverage = "-" if row["coverage_rate"] is None else f"{row['coverage_rate']:.1%}"
        print(
            f"{row['target']:<5} {row['version_label']:<28} {row['lifecycle_status']:<10} "
            f"pred={row['prediction_count']:<5} resolved={row['resolved_count']:<5} pos={row['positive_count']:<4} "
            f"coverage={coverage:<7} health={row['health_status']}"
        )
        print(
            f"      performance={row['performance_status']} drift={row['drift_status']} "
            f"brier={row['brier_score']} ece={row['ece']} pred_psi={row['prediction_psi']} "
            f"max_feature_psi={row['max_feature_psi']}"
        )
        reasons = row["health_reasons"] or []
        if isinstance(reasons, str):
            print(f"      reasons={reasons}")
        else:
            for reason in reasons:
                print(f"      - {reason}")
    print("=" * 110)


if __name__ == "__main__":
    main()
