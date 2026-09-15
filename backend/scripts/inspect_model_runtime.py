#!/usr/bin/env python3
"""Inspect the live registry-driven model runtime without changing registry state."""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.dog import Dog  # noqa: E402
from app.services.potty_prediction import (  # noqa: E402
    current_model_probabilities,
    get_training_bundle,
)


def pick_dog(db, dog_id: str | None) -> Dog:
    if dog_id:
        dog = db.get(Dog, uuid.UUID(dog_id))
        if dog is None:
            raise SystemExit("Dog not found.")
        return dog

    dogs = list(db.query(Dog).order_by(Dog.created_at.asc()).all())
    if len(dogs) == 1:
        return dogs[0]
    if not dogs:
        raise SystemExit("No dogs found.")

    print("Multiple dogs found. Re-run with --dog-id:")
    for dog in dogs:
        print(f"  {dog.id}  {dog.name}")
    raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dog-id", default=None)
    parser.add_argument("--timezone", default="America/Chicago")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        dog = pick_dog(db, args.dog_id)
        bundle = get_training_bundle(
            db,
            dog.id,
            args.timezone,
            now,
        )
        probabilities, _ = current_model_probabilities(
            bundle,
            now,
        )

    print()
    print("=" * 90)
    print(f"PawPredict registry runtime — {dog.name}")
    print("=" * 90)

    for target in ("ANY", "PEE", "POOP"):
        fitted = bundle.models[target]
        config = fitted.config
        print(
            f"{target:<5}  "
            f"{config.version_label:<30} "
            f"source={config.source:<15} "
            f"window={config.training_window_days:>2}d "
            f"features={len(config.feature_names):>2} "
            f"cal={config.calibration_method:<8} "
            f"p={probabilities[target]:.4f}"
        )

    print()
    print("Expected before Poop V2 promotion:")
    print("  ANY  -> v1-any-full-60d")
    print("  PEE  -> v1-pee-full-60d")
    print("  POOP -> v1-poop-full-60d")
    print("=" * 90)


if __name__ == "__main__":
    main()
