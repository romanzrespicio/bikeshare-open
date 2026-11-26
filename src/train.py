"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
"""
import argparse
import json

import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import METRICS, PROCESSED, TARGET, TRAIN_END, VALID_END
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def fit_and_score() -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    for name, model in MODELS.items():
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in [("valid", valid), ("test", test)]
        }
    return results


def fit_and_score_ratio(with_test: bool) -> dict:
    """Fit on y_t = cnt / cnt_roll_7 and score on cnt in rides."""
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)

    splits = [("valid", valid)]
    if with_test:
        splits.append(("test", test))

    ratio_target = train[TARGET] / train["cnt_roll_7"]
    models = {
        "baseline_mean": DummyRegressor(strategy="mean"),
        "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
    }

    results = {}
    for name, model in models.items():
        if name != "baseline_persistence":
            model.fit(train[cols], ratio_target)
        results[name] = {}
        for split, part in splits:
            if name == "baseline_persistence":
                y_pred = part["cnt_lag_1"].to_numpy(dtype=float)
            else:
                y_pred = model.predict(part[cols]) * part["cnt_roll_7"].to_numpy(dtype=float)
            results[name][split] = {
                "r2": round(float(r2_score(part[TARGET], y_pred)), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], y_pred)), 1),
            }
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train models and report metrics.")
    parser.add_argument("--target-transform", choices=["ratio"], help="Transform target before fitting.")
    parser.add_argument("--with-test", action="store_true", help="Include test metrics (only with --target-transform).")
    args = parser.parse_args()

    if args.target_transform == "ratio":
        res = fit_and_score_ratio(with_test=args.with_test)
        print(json.dumps(res, indent=2))
    else:
        res = fit_and_score()
        METRICS.parent.mkdir(parents=True, exist_ok=True)
        METRICS.write_text(json.dumps(res, indent=2))
        print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
