"""Train an interpretable baseline once a feature table has enough examples."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "minutes_since_pee", "minutes_since_poop", "minutes_since_potty_attempt",
    "pee_count_today", "poop_count_today", "recent_treat_30m", "recent_zoomies_30m",
    "hour_sin", "hour_cos", "age_days",
]


def main(path: Path) -> None:
    df = pd.read_csv(path)
    if df["target_10m"].sum() < 20:
        raise SystemExit("Not enough positive potty windows yet; keep collecting data before trusting a fitted model.")
    split = int(len(df) * 0.8)
    train, test = df.iloc[:split], df.iloc[split:]
    pipeline = Pipeline([
        ("prep", ColumnTransformer([("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), FEATURES)])),
        ("model", LogisticRegression(class_weight="balanced", max_iter=2000)),
    ])
    pipeline.fit(train[FEATURES], train["target_10m"])
    prob = pipeline.predict_proba(test[FEATURES])[:, 1]
    pred = (prob >= 0.5).astype(int)
    print(classification_report(test["target_10m"], pred, zero_division=0))
    if test["target_10m"].nunique() > 1:
        print("ROC-AUC:", round(roc_auc_score(test["target_10m"], prob), 3))
    print("PR-AUC:", round(average_precision_score(test["target_10m"], prob), 3))
    print("Brier:", round(brier_score_loss(test["target_10m"], prob), 3))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_csv", type=Path)
    main(parser.parse_args().feature_csv)
