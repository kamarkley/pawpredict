from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.services.model_monitoring import DEFAULT_WINDOWS, run_monitoring


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute PawPredict production ML monitoring snapshots from the prediction ledger."
    )
    parser.add_argument(
        "--dog-id",
        default=None,
        help="Optional dog UUID. Omit to monitor every dog with PRODUCTION/SHADOW models.",
    )
    parser.add_argument(
        "--windows",
        nargs="+",
        type=int,
        default=list(DEFAULT_WINDOWS),
        help="Rolling monitoring windows in days. Default: 7 14 30.",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Optional ISO-8601 timestamp for reproducible runs. Default: now (UTC).",
    )
    return parser.parse_args()


def _parse_as_of(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def main() -> None:
    args = _parse_args()
    as_of = _parse_as_of(args.as_of)

    with SessionLocal() as db:
        results = run_monitoring(
            db,
            dog_id=args.dog_id,
            as_of=as_of,
            windows=args.windows,
        )

    if not results:
        print("No PRODUCTION or SHADOW model versions were found for the requested scope.")
        return

    print("=" * 118)
    print(f"PawPredict model monitoring — as of {as_of.isoformat()}")
    print("=" * 118)
    print(
        f"{'TARGET':<7} {'VERSION':<28} {'STATE':<11} {'WIN':>4} "
        f"{'PRED':>6} {'RES':>6} {'POS':>5} {'COV':>7} {'BRIER':>8} {'ECE':>7} {'PSI':>7} {'HEALTH':<18}"
    )
    print("-" * 118)

    for row in results:
        coverage = "-" if row["coverage_rate"] is None else f"{row['coverage_rate']:.1%}"
        print(
            f"{row['target']:<7} "
            f"{row['version_label']:<28} "
            f"{row['lifecycle_status']:<11} "
            f"{row['window_days']:>3}d "
            f"{row['prediction_count']:>6} "
            f"{row['resolved_count']:>6} "
            f"{row['positive_count']:>5} "
            f"{coverage:>7} "
            f"{_fmt(row['brier_score']):>8} "
            f"{_fmt(row['ece'], 3):>7} "
            f"{_fmt(row['prediction_psi'], 3):>7} "
            f"{row['health_status']:<18}"
        )

    print("=" * 118)
    print("INSUFFICIENT_DATA is expected early: the monitoring system does not fabricate a historical live baseline.")
    print("Run the outcome resolver before this job so recently closed prediction horizons are scored first.")


if __name__ == "__main__":
    main()
