from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")

from ml.features import CATEGORICAL_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES, TARGET, metrics_dict, prepare_training_frame
from ml.train import build_model

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUT_DIR = PROCESSED_DIR / "model_comparison"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_preprocessor():
    return ColumnTransformer(
        transformers=[
            (
                "categorical",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-1),
                CATEGORICAL_FEATURES,
            ),
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def candidate_models(random_state=42):
    return {
        "ExtraTreesRegressor": build_model(random_state=random_state),
        "RandomForestRegressor": Pipeline(
            [
                ("preprocess", make_preprocessor()),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=45,
                        max_depth=16,
                        min_samples_leaf=4,
                        max_features=0.85,
                        random_state=random_state,
                        n_jobs=2,
                    ),
                ),
            ]
        ),
        "HistGradientBoostingRegressor": Pipeline(
            [
                ("preprocess", make_preprocessor()),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        max_iter=130,
                        learning_rate=0.08,
                        max_leaf_nodes=31,
                        l2_regularization=0.05,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
    }


def save_metric_chart(results):
    df = pd.DataFrame(results)
    plot_df = df.melt(
        id_vars="model_name",
        value_vars=["MAE", "RMSE", "WAPE_percent", "MAPE_percent"],
        var_name="metric",
        value_name="value",
    )

    plt.rcParams.update(
        {
            "figure.facecolor": "#f6f8fb",
            "axes.facecolor": "white",
            "axes.edgecolor": "#d7dde8",
            "axes.grid": True,
            "grid.color": "#e7ebf2",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    metrics = ["MAE", "RMSE", "WAPE_percent", "MAPE_percent"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    axes = axes.flatten()
    for ax, metric in zip(axes, metrics):
        part = plot_df[plot_df["metric"] == metric].sort_values("value")
        colors = ["#2ca02c" if i == 0 else "#1f77b4" for i in range(len(part))]
        ax.barh(part["model_name"], part["value"], color=colors)
        ax.set_title(metric)
        ax.set_xlabel("lower is better")
    fig.suptitle("Forecast model comparison on holdout", fontweight="bold")
    fig.tight_layout()
    out = OUT_DIR / "model_comparison_metrics.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def compare_forecast_models(max_train_rows=70000, max_test_rows=25000, random_state=42):
    sales = pd.read_csv(RAW_DIR / "sales_history.csv")
    df = prepare_training_frame(sales)
    df["date"] = pd.to_datetime(df["date"])

    max_date = df["date"].max()
    cutoff = max_date - pd.Timedelta(days=90)
    train_df = df[df["date"] <= cutoff].copy()
    test_df = df[df["date"] > cutoff].copy()

    if len(train_df) > max_train_rows:
        train_df = train_df.sample(max_train_rows, random_state=random_state)
    if len(test_df) > max_test_rows:
        test_df = test_df.sample(max_test_rows, random_state=random_state)

    results = []
    baseline_pred = np.clip(
        test_df["rolling_mean_14"].fillna(test_df["rolling_mean_7"]).fillna(train_df[TARGET].mean()).to_numpy(),
        0,
        None,
    )
    baseline_metrics = metrics_dict(test_df[TARGET], baseline_pred)
    baseline_metrics["R2"] = round(float(r2_score(test_df[TARGET], baseline_pred)), 4)
    results.append({"model_name": "Baseline rolling_mean_14", **baseline_metrics})

    for name, model in candidate_models(random_state=random_state).items():
        model.fit(train_df[FEATURE_COLUMNS], train_df[TARGET])
        pred = np.clip(model.predict(test_df[FEATURE_COLUMNS]), 0, None)
        model_metrics = metrics_dict(test_df[TARGET], pred)
        model_metrics["R2"] = round(float(r2_score(test_df[TARGET], pred)), 4)
        results.append({"model_name": name, **model_metrics})

    results_df = pd.DataFrame(results).sort_values("WAPE_percent")
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "holdout_start_date": (cutoff + pd.Timedelta(days=1)).date().isoformat(),
        "holdout_end_date": max_date.date().isoformat(),
        "train_rows_used": int(len(train_df)),
        "test_rows_used": int(len(test_df)),
        "best_model_by_WAPE": results_df.iloc[0]["model_name"],
        "results": results_df.to_dict("records"),
    }

    results_df.to_csv(OUT_DIR / "model_comparison_metrics.csv", index=False)
    (OUT_DIR / "model_comparison_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    save_metric_chart(results_df.to_dict("records"))
    return payload


if __name__ == "__main__":
    output = compare_forecast_models()
    print(json.dumps(output, indent=2))
