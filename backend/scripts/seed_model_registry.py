#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.dog import Dog  # noqa: E402
from app.services.model_registry import (  # noqa: E402
    upsert_evaluation,
    upsert_model_version,
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
    parser.add_argument(
        "--seed",
        type=Path,
        default=REPO_ROOT / "database" / "model_registry_seed.json",
    )
    args = parser.parse_args()

    payload = json.loads(args.seed.read_text(encoding="utf-8"))
    evaluation = payload["prospective_shadow"]

    with SessionLocal() as db:
        dog = pick_dog(db, args.dog_id)

        for config in payload["models"]:
            metrics = config["metrics"]

            version = upsert_model_version(
                db,
                dog_id=dog.id,
                target=config["target"],
                version_label=config["version_label"],
                model_family=config["model_family"],
                status=config["status"],
                feature_names=config["feature_names"],
                training_window_days=config["training_window_days"],
                sample_weight_half_life_days=config["sample_weight_half_life_days"],
                calibration_method=config["calibration_method"],
                config_json={
                    "source": "pawpredict_30_day_model_program",
                    "retrain_mode": "dynamic_from_database",
                    "decision_reason": config["decision_reason"],
                },
                reason=config["decision_reason"],
                actor="Kenzie/model-validation",
            )

            upsert_evaluation(
                db,
                model_version_id=version.id,
                evaluation_key=evaluation["evaluation_key"],
                evaluation_type=evaluation["evaluation_type"],
                window_start=datetime.fromisoformat(evaluation["window_start"]),
                window_end=datetime.fromisoformat(evaluation["window_end"]),
                snapshot_count=evaluation["snapshot_count"],
                positive_count=metrics["positive_count"],
                prevalence=metrics["prevalence"],
                pr_auc=metrics["pr_auc"],
                roc_auc=metrics["roc_auc"],
                brier_score=metrics["brier_score"],
                ece=metrics["ece"],
                calibration_intercept=metrics["calibration_intercept"],
                calibration_slope=metrics["calibration_slope"],
                metrics_json={
                    "decision_reason": config["decision_reason"],
                },
            )

        db.commit()
        print(f"Seeded PawPredict model registry for {dog.name}.")
        print("Current intended registry state:")
        print("  ANY  v1 = PRODUCTION; v2 = REJECTED")
        print("  PEE  v1 = PRODUCTION; v2 = REJECTED")
        print("  POOP v1 = PRODUCTION; v2 = CANDIDATE")
        print()
        print("Poop V2 stays CANDIDATE until the production prediction service")
        print("actually uses its 30-day / 4-feature configuration.")


if __name__ == "__main__":
    main()
