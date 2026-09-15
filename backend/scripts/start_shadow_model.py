#!/usr/bin/env python3
"""Move a registered candidate into SHADOW status."""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.dog import Dog
from app.services.model_registry import (  # noqa: E402
    change_status,
    get_model_by_label,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dog-id", required=True)
    parser.add_argument(
        "--target",
        choices=["ANY", "PEE", "POOP"],
        required=True,
    )
    parser.add_argument("--version-label", required=True)
    parser.add_argument(
        "--reason",
        default="Started silent champion/challenger shadow scoring.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        version = get_model_by_label(
            db,
            uuid.UUID(args.dog_id),
            args.target,
            args.version_label,
        )
        if version is None:
            raise SystemExit("Model version not found.")

        if version.status not in {"CANDIDATE", "SHADOW"}:
            raise SystemExit(
                f"Expected CANDIDATE/SHADOW, found {version.status}. "
                "Do not shadow a rejected or production model accidentally."
            )

        change_status(
            db,
            version,
            new_status="SHADOW",
            reason=args.reason,
            actor="manual-cli",
        )
        db.commit()

        print(
            f"{args.target} / {args.version_label} is now SHADOW."
        )


if __name__ == "__main__":
    main()
