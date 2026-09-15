#!/usr/bin/env python3
"""Resolve matured PawPredict champion/shadow prediction outcomes."""
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
from app.services.potty_prediction import get_training_bundle  # noqa: E402
from app.services.prediction_ledger import resolve_pending_predictions  # noqa: E402


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
    parser.add_argument("--limit", type=int, default=5000)
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
        result = resolve_pending_predictions(
            db,
            bundle,
            now,
            limit=args.limit,
        )
        db.commit()

    print(f"Outcome resolution complete for {dog.name}:")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
