#!/usr/bin/env python3
"""
Manual/controlled model promotion.

Do not run this merely because a candidate has good metrics. Promote only after
the PawPredict inference service is configured to actually execute that version.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.model_registry import (  # noqa: E402
    get_model_by_label,
    promote_to_production,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dog-id", required=True)
    parser.add_argument("--target", choices=["ANY", "PEE", "POOP"], required=True)
    parser.add_argument("--version-label", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    with SessionLocal() as db:
        model = get_model_by_label(
            db,
            uuid.UUID(args.dog_id),
            args.target,
            args.version_label,
        )
        if model is None:
            raise SystemExit("Model version not found.")

        promote_to_production(
            db,
            model,
            reason=args.reason,
            actor="manual-cli",
        )
        db.commit()

        print(
            f"Promoted {args.target} / {args.version_label} to PRODUCTION."
        )


if __name__ == "__main__":
    main()
