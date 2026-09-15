#!/usr/bin/env python3
"""Freeze PawPredict Phase 5C survival challengers for prospective validation."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.dog import Dog  # noqa: F401,E402
from app.database import SessionLocal  # noqa: E402
from app.services.potty_prediction import get_training_bundle  # noqa: E402
from app.services.time_to_event_prospective import (  # noqa: E402
    fit_frozen_bundle,
    save_frozen_bundle,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dog-id", required=True)
    parser.add_argument("--timezone", default="America/Chicago")
    parser.add_argument(
        "--output",
        default="time_to_event_prospective/frozen_challengers.pkl",
    )
    args = parser.parse_args()

    dog_id = uuid.UUID(args.dog_id)
    with SessionLocal() as db:
        bundle = get_training_bundle(db, dog_id, args.timezone)
        frozen = fit_frozen_bundle(bundle, str(dog_id), args.timezone)

    destination = save_frozen_bundle(frozen, args.output)
    sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest_path = destination.with_suffix(destination.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps({
        "artifact": destination.name,
        "sha256": sha256,
        "artifact_version": frozen.artifact_version,
        "dog_id": frozen.dog_id,
        "timezone_name": frozen.timezone_name,
        "frozen_at": frozen.frozen_at.isoformat(),
        "candidates": {
            target: {
                "label": candidate.spec.label,
                "horizon_minutes": candidate.spec.horizon_minutes,
                "feature_set": candidate.spec.feature_set,
                "feature_names": list(candidate.spec.feature_names),
                "training_landmarks": candidate.training_landmarks,
                "training_events": candidate.training_events,
                "km_median_minutes": candidate.km_median_minutes,
            }
            for target, candidate in frozen.candidates.items()
        },
    }, indent=2) + "\n")
    print("=" * 108)
    print("PawPredict Phase 5C — frozen prospective survival challengers")
    print("=" * 108)
    print(f"Frozen at: {frozen.frozen_at.isoformat()}")
    print(f"Artifact:  {destination.resolve()}")
    print(f"SHA-256:   {sha256}")
    print(f"Manifest:  {manifest_path.resolve()}")
    print()
    for target in ("PEE", "POOP"):
        candidate = frozen.candidates[target]
        print(
            f"{target:<5} {candidate.spec.label:<24} "
            f"train={candidate.training_landmarks:<5} events={candidate.training_events:<4} "
            f"KM median={candidate.km_median_minutes} min"
        )
    print("=" * 108)
    print("DO NOT overwrite this artifact. Future validation must use this exact frozen model bundle.")


if __name__ == "__main__":
    main()
