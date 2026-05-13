from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from ml.features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    TARGET,
    metrics_dict,
    prepare_training_frame,
)


def _make_categorical_encoder() -> OrdinalEncoder:
    return OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-1)


def build_model(random_state: int = 42) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", _make_categorical_encoder(), CATEGORICAL_FEATURES),
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    model = ExtraTreesRegressor(
        n_estimators=60,
        max_depth=16,
        min_samples_leaf=3,
        max_features=0.85,
        random_state=random_state,
        n_jobs=2,
    )
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def build_sale_probability_model(random_state: int = 42) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", _make_categorical_encoder(), CATEGORICAL_FEATURES),
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    model = ExtraTreesClassifier(
        n_estimators=70,
        max_depth=14,
        min_samples_leaf=4,
        max_features=0.85,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=2,
    )
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def build_positive_quantity_model(random_state: int = 42) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", _make_categorical_encoder(), CATEGORICAL_FEATURES),
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    model = ExtraTreesRegressor(
        n_estimators=70,
        max_depth=14,
        min_samples_leaf=3,
        max_features=0.85,
        random_state=random_state,
        n_jobs=2,
    )
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def _sample_frame(df: pd.DataFrame, max_rows: int, random_state: int) -> pd.DataFrame:
    if len(df) <= max_rows:
        return df
    return df.sample(n=max_rows, random_state=random_state)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pair_key(sku: str, location_id: str) -> str:
    return f"{sku}||{location_id}"


def _wape(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.sum(np.abs(y_true - y_pred)) / max(1e-9, np.sum(np.abs(y_true))) * 100)


def _mae(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred))) if len(y_true) else 0.0


def _candidate_baseline(row: pd.Series) -> float:
    for col in ["rolling_mean_28", "rolling_mean_14", "rolling_mean_7", "lag_7", "lag_1"]:
        value = row.get(col)
        if pd.notna(value):
            return max(0.0, float(value))
    return 0.0


def _build_pair_profiles(train_df: pd.DataFrame) -> pd.DataFrame:
    daily = (
        train_df.groupby(["sku", "location_id"], as_index=False)
        .agg(
            category=("category", "first"),
            climate_zone=("climate_zone", "first"),
            avg_daily_sales=(TARGET, "mean"),
            std_daily_sales=(TARGET, "std"),
            zero_sales_share=(TARGET, lambda s: float((s <= 0).mean())),
            positive_sales_share=(TARGET, lambda s: float((s > 0).mean())),
            total_units=(TARGET, "sum"),
            n_days=(TARGET, "size"),
        )
    )
    daily["cv_demand"] = daily["std_daily_sales"].fillna(0) / (daily["avg_daily_sales"].abs() + 1e-6)
    daily["demand_segment"] = np.select(
        [
            (daily["avg_daily_sales"] >= 2.0) & (daily["zero_sales_share"] < 0.35),
            (daily["zero_sales_share"] >= 0.55) | (daily["avg_daily_sales"] < 0.75),
            daily["cv_demand"] >= 1.0,
        ],
        ["high_volume", "rare_intermittent", "volatile"],
        default="regular",
    )
    weather_categories = {"winter_fluids", "battery", "wipers", "ac_cooling", "coolant"}
    daily["is_weather_sensitive_category"] = daily["category"].isin(weather_categories)
    daily["is_two_stage_candidate"] = (
        daily["demand_segment"].isin(["rare_intermittent", "volatile"])
        & (daily["total_units"] >= 20)
        & (daily["positive_sales_share"] > 0.03)
    )
    return daily


def _pair_profile_lookup(pair_profiles: pd.DataFrame) -> Dict[str, dict]:
    if pair_profiles.empty:
        return {}
    return {
        _pair_key(str(row.sku), str(row.location_id)): row._asdict()
        for row in pair_profiles.itertuples(index=False)
    }


def _predict_sale_probability(model: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(frame[FEATURE_COLUMNS])
        classes = list(model.named_steps["model"].classes_)
        if 1 in classes:
            return proba[:, classes.index(1)]
        return proba[:, -1]
    return np.clip(model.predict(frame[FEATURE_COLUMNS]), 0, 1)


def _two_stage_predictions(
    frame: pd.DataFrame,
    sale_model: Pipeline,
    positive_model: Pipeline,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sale_probability = np.clip(_predict_sale_probability(sale_model, frame), 0, 1)
    conditional_quantity = np.clip(positive_model.predict(frame[FEATURE_COLUMNS]), 0, None)
    two_stage_prediction = sale_probability * conditional_quantity
    return sale_probability, conditional_quantity, two_stage_prediction


def _learn_two_stage_policy(
    calib_df: pd.DataFrame,
    pair_profiles: pd.DataFrame,
    min_rows: int = 21,
) -> Dict[str, object]:
    profile_lookup = _pair_profile_lookup(pair_profiles)
    by_pair: Dict[str, object] = {}
    by_category: Dict[str, object] = {}

    def learn_group(group: pd.DataFrame) -> Dict[str, object]:
        y = group[TARGET].to_numpy(dtype=float)
        global_pred = group["calibrated_prediction"].to_numpy(dtype=float)
        two_stage_pred = group["two_stage_prediction"].to_numpy(dtype=float)
        global_wape = _wape(y, global_pred)
        two_stage_wape = _wape(y, two_stage_pred)
        improvement_pp = global_wape - two_stage_wape
        enabled = bool(improvement_pp >= 4.0 and group[TARGET].sum() >= 5)
        return {
            "enabled": enabled,
            "global_wape_percent": round(global_wape, 4),
            "two_stage_wape_percent": round(two_stage_wape, 4),
            "improvement_pp": round(float(improvement_pp), 4),
            "target_units": round(float(group[TARGET].sum()), 4),
            "n_rows": int(len(group)),
        }

    for (sku, location_id), group in calib_df.groupby(["sku", "location_id"], sort=False):
        key = _pair_key(str(sku), str(location_id))
        profile = profile_lookup.get(key, {})
        if not profile.get("is_two_stage_candidate", False) or len(group) < min_rows:
            continue
        by_pair[key] = learn_group(group)

    for category, group in calib_df.groupby("category", sort=False):
        if len(group) < min_rows or group[TARGET].sum() < 10:
            continue
        candidate_share = group.apply(lambda r: profile_lookup.get(_pair_key(str(r["sku"]), str(r["location_id"])), {}).get("is_two_stage_candidate", False), axis=1).mean()
        if candidate_share >= 0.35:
            by_category[str(category)] = learn_group(group)

    return {"by_pair": by_pair, "by_category": by_category}


def apply_two_stage_policy(eval_df: pd.DataFrame, policy: Dict[str, object]) -> tuple[pd.Series, pd.Series]:
    by_pair = policy.get("by_pair", {})
    by_category = policy.get("by_category", {})
    values = []
    scopes = []
    for _, row in eval_df.iterrows():
        key = _pair_key(str(row["sku"]), str(row["location_id"]))
        stats = by_pair.get(key)
        scope = "global_local"
        if stats is not None and stats.get("enabled", False):
            values.append(max(0.0, float(row["two_stage_prediction"])))
            scopes.append("two_stage_sku_location")
            continue
        stats = by_category.get(str(row.get("category", "")))
        if stats is not None and stats.get("enabled", False):
            values.append(max(0.0, float(row["two_stage_prediction"])))
            scopes.append("two_stage_category")
            continue
        values.append(max(0.0, float(row["calibrated_prediction"])))
        scopes.append(scope)
    return pd.Series(values, index=eval_df.index), pd.Series(scopes, index=eval_df.index)


def _learn_local_calibration(calib_df: pd.DataFrame, min_rows: int = 21) -> Dict[str, object]:
    """Learn a light local layer per SKU-location.

    The global model remains the main learner; this local layer chooses a blend
    between global ML and the local rolling baseline, then applies a conservative
    scale correction. It is intentionally small so sparse SKU-location series do
    not overfit.
    """
    weights = [0.55, 0.70, 0.85, 1.00]
    by_pair: Dict[str, object] = {}
    by_category: Dict[str, object] = {}

    frame = calib_df.copy()
    frame["local_baseline"] = frame.apply(_candidate_baseline, axis=1)

    def learn_group(group: pd.DataFrame) -> Dict[str, float]:
        y = group[TARGET].astype(float).to_numpy()
        raw = group["raw_prediction"].astype(float).to_numpy()
        baseline = group["local_baseline"].astype(float).to_numpy()
        target_sum = float(np.sum(y))
        best_weight = 1.0
        best_pred = raw
        raw_wape = _wape(y, raw)
        best_wape = raw_wape
        for weight in weights:
            cand = np.clip(weight * raw + (1.0 - weight) * baseline, 0, None)
            cand_wape = _wape(y, cand)
            if cand_wape < best_wape:
                best_weight = weight
                best_wape = cand_wape
                best_pred = cand
        scale = float(np.sum(y) / max(1e-6, np.sum(best_pred)))
        scale = float(np.clip(scale, 0.70, 1.35))
        scaled = np.clip(best_pred * scale, 0, None)
        scaled_wape = _wape(y, scaled)
        improvement_pp = raw_wape - scaled_wape
        stable_volume = target_sum >= 35 or float(np.mean(y)) >= 0.75
        conservative_scale = 0.85 <= scale <= 1.18
        enabled = bool(stable_volume and conservative_scale and improvement_pp >= 3.0)
        if not enabled:
            best_weight = 1.0
            scale = 1.0
            scaled = raw
            scaled_wape = raw_wape
        return {
            "global_weight": round(float(best_weight), 4),
            "scale_factor": round(scale, 4),
            "bias_units": round(float(np.mean(y - scaled)), 4),
            "calibration_wape_percent": round(scaled_wape, 4),
            "raw_wape_percent": round(raw_wape, 4),
            "improvement_pp": round(float(raw_wape - scaled_wape), 4),
            "target_units": round(target_sum, 4),
            "enabled": enabled,
            "n_rows": int(len(group)),
        }

    for (sku, location_id), group in frame.groupby(["sku", "location_id"], sort=False):
        if len(group) >= min_rows and group[TARGET].sum() > 0:
            by_pair[_pair_key(str(sku), str(location_id))] = learn_group(group)

    for category, group in frame.groupby("category", sort=False):
        if len(group) >= min_rows and group[TARGET].sum() > 0:
            by_category[str(category)] = learn_group(group)

    global_stats = learn_group(frame) if len(frame) else {
        "global_weight": 1.0,
        "scale_factor": 1.0,
        "bias_units": 0.0,
        "calibration_wape_percent": 0.0,
        "raw_wape_percent": 0.0,
        "n_rows": 0,
    }
    return {"by_pair": by_pair, "by_category": by_category, "global": global_stats}


def apply_local_calibration(eval_df: pd.DataFrame, calibration: Dict[str, object]) -> pd.Series:
    by_pair = calibration.get("by_pair", {})
    by_category = calibration.get("by_category", {})
    global_stats = calibration.get("global", {"global_weight": 1.0, "scale_factor": 1.0})
    values = []
    for _, row in eval_df.iterrows():
        key = _pair_key(str(row["sku"]), str(row["location_id"]))
        stats = by_pair.get(key) or by_category.get(str(row.get("category", ""))) or global_stats
        baseline = _candidate_baseline(row)
        raw = max(0.0, float(row["raw_prediction"]))
        if stats and not bool(stats.get("enabled", True)):
            values.append(raw)
            continue
        weight = float(stats.get("global_weight", 1.0))
        scale = float(stats.get("scale_factor", 1.0))
        pred = (weight * raw + (1.0 - weight) * baseline) * scale
        values.append(max(0.0, float(pred)))
    return pd.Series(values, index=eval_df.index)


def _calibration_rows(calibration: Dict[str, object]) -> pd.DataFrame:
    rows = []
    for key, stats in calibration.get("by_pair", {}).items():
        sku, location_id = key.split("||", 1)
        rows.append({"scope": "sku_location", "sku": sku, "location_id": location_id, **stats})
    for category, stats in calibration.get("by_category", {}).items():
        rows.append({"scope": "category", "category": category, **stats})
    rows.append({"scope": "global", **calibration.get("global", {})})
    return pd.DataFrame(rows)


def _metrics_row(name: str, frame: pd.DataFrame, pred_col: str = "prediction") -> Dict[str, object]:
    if frame.empty:
        return {"segment": name, "n_rows": 0, "actual_units": 0.0, "predicted_units": 0.0, "MAE": 0.0, "WAPE_percent": 0.0, "bias_units": 0.0}
    y = frame[TARGET].astype(float)
    pred = frame[pred_col].astype(float)
    return {
        "segment": name,
        "n_rows": int(len(frame)),
        "actual_units": round(float(y.sum()), 4),
        "predicted_units": round(float(pred.sum()), 4),
        "MAE": round(_mae(y, pred), 4),
        "WAPE_percent": round(_wape(y, pred), 4),
        "bias_units": round(float((pred - y).mean()), 4),
    }


def _add_pair_profiles(frame: pd.DataFrame, pair_profiles: pd.DataFrame) -> pd.DataFrame:
    if pair_profiles.empty:
        return frame.copy()
    keep = [
        "sku",
        "location_id",
        "avg_daily_sales",
        "zero_sales_share",
        "cv_demand",
        "demand_segment",
        "is_weather_sensitive_category",
        "is_two_stage_candidate",
    ]
    return frame.merge(pair_profiles[[c for c in keep if c in pair_profiles.columns]], on=["sku", "location_id"], how="left")


def _aggregate_21d(frame: pd.DataFrame, pred_col: str = "prediction") -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"])
    start = data["date"].min()
    data["window_index"] = ((data["date"] - start).dt.days // 21).astype(int)
    agg = (
        data.groupby(["sku", "location_id", "window_index"], as_index=False)
        .agg(
            category=("category", "first"),
            climate_zone=("climate_zone", "first"),
            date_start=("date", "min"),
            date_end=("date", "max"),
            quantity_sold=(TARGET, "sum"),
            prediction=(pred_col, "sum"),
            raw_prediction=("raw_prediction", "sum"),
            baseline_prediction=("baseline_prediction", "sum"),
            avg_daily_sales=("avg_daily_sales", "first"),
            zero_sales_share=("zero_sales_share", "first"),
            cv_demand=("cv_demand", "first"),
            demand_segment=("demand_segment", "first"),
            is_weather_sensitive_category=("is_weather_sensitive_category", "first"),
            stockout_days=("stockout_flag", "sum") if "stockout_flag" in data.columns else (TARGET, "size"),
            weather_spike_days=("weather_spike_flag", "sum") if "weather_spike_flag" in data.columns else (TARGET, "size"),
            cold_snap_days=("cold_snap_flag", "sum") if "cold_snap_flag" in data.columns else (TARGET, "size"),
            heatwave_days=("heatwave_flag", "sum") if "heatwave_flag" in data.columns else (TARGET, "size"),
            starting_stock=("stock_on_hand_end", "first") if "stock_on_hand_end" in data.columns else (TARGET, "size"),
        )
    )
    if "stockout_flag" not in data.columns:
        agg["stockout_days"] = 0
    if "weather_spike_flag" not in data.columns:
        agg["weather_spike_days"] = 0
    if "cold_snap_flag" not in data.columns:
        agg["cold_snap_days"] = 0
    if "heatwave_flag" not in data.columns:
        agg["heatwave_days"] = 0
    if "stock_on_hand_end" not in data.columns:
        agg["starting_stock"] = np.nan
    return agg


def build_segmented_metrics(eval_daily: pd.DataFrame, processed_path: Path) -> tuple[list[dict], list[dict], pd.DataFrame]:
    daily_rows = [_metrics_row("overall_daily", eval_daily)]
    segments = {
        "high_volume_daily": eval_daily["demand_segment"].eq("high_volume"),
        "rare_intermittent_daily": eval_daily["demand_segment"].eq("rare_intermittent"),
        "volatile_daily": eval_daily["demand_segment"].eq("volatile"),
        "weather_sensitive_category_daily": eval_daily["is_weather_sensitive_category"].fillna(False).astype(bool),
    }
    for name, mask in segments.items():
        daily_rows.append(_metrics_row(name, eval_daily[mask]))

    agg21 = _aggregate_21d(eval_daily)
    horizon_rows = [_metrics_row("overall_21d", agg21)]
    horizon_segments = {
        "high_volume_21d": agg21["demand_segment"].eq("high_volume"),
        "rare_intermittent_21d": agg21["demand_segment"].eq("rare_intermittent"),
        "volatile_21d": agg21["demand_segment"].eq("volatile"),
        "weather_sensitive_category_21d": agg21["is_weather_sensitive_category"].fillna(False).astype(bool),
    }
    for name, mask in horizon_segments.items():
        horizon_rows.append(_metrics_row(name, agg21[mask]))

    pd.DataFrame(daily_rows).to_csv(processed_path / "segmented_daily_metrics.csv", index=False)
    pd.DataFrame(horizon_rows).to_csv(processed_path / "segmented_21d_metrics.csv", index=False)
    agg21.to_csv(processed_path / "holdout_21d_predictions.csv", index=False)
    return daily_rows, horizon_rows, agg21


def build_business_backtest(agg21: pd.DataFrame, processed_path: Path) -> tuple[dict, pd.DataFrame]:
    if agg21.empty:
        summary = {"status": "empty"}
        return summary, pd.DataFrame()
    bt = agg21.copy()
    bt["baseline_units"] = bt["baseline_prediction"].fillna(0)
    bt["weather_trigger_days"] = bt[["weather_spike_days", "cold_snap_days", "heatwave_days"]].fillna(0).sum(axis=1)
    bt["actual_spike"] = (bt["quantity_sold"] >= np.maximum(bt["baseline_units"] * 1.20, bt["baseline_units"] + 3)).astype(int)
    bt["predicted_spike"] = (bt["prediction"] >= np.maximum(bt["baseline_units"] * 1.20, bt["baseline_units"] + 3)).astype(int)
    bt["rank_score"] = (
        (bt["prediction"] - bt["baseline_units"]).clip(lower=0) * 2.0
        + bt["weather_trigger_days"] * 2.5
        + bt["is_weather_sensitive_category"].fillna(False).astype(int) * 4.0
        + bt["cv_demand"].fillna(0).clip(0, 3) * 2.0
    )
    top_threshold = bt["rank_score"].quantile(0.75)
    bt["ranked_alert"] = (bt["rank_score"] >= max(8.0, top_threshold)).astype(int)
    bt["stockout_risk_actual"] = ((bt["stockout_days"] > 0) | (bt["quantity_sold"] > bt["starting_stock"].fillna(np.inf))).astype(int)
    bt["stockout_risk_predicted"] = (bt["prediction"] > bt["starting_stock"].fillna(np.inf) * 0.90).astype(int)
    bt["action_alert"] = ((bt["ranked_alert"] == 1) | (bt["stockout_risk_predicted"] == 1)).astype(int)
    bt["true_positive_alert"] = ((bt["action_alert"] == 1) & ((bt["actual_spike"] == 1) | (bt["stockout_risk_actual"] == 1))).astype(int)
    bt["false_positive_alert"] = ((bt["action_alert"] == 1) & (bt["actual_spike"] == 0) & (bt["stockout_risk_actual"] == 0)).astype(int)
    bt["false_negative_alert"] = ((bt["action_alert"] == 0) & ((bt["actual_spike"] == 1) | (bt["stockout_risk_actual"] == 1))).astype(int)
    bt["potential_stockout_units"] = (bt["quantity_sold"] - bt["starting_stock"].fillna(np.inf)).clip(lower=0)
    bt["predicted_shortage_units"] = (bt["prediction"] - bt["starting_stock"].fillna(np.inf)).clip(lower=0)
    bt["stockout_units_flagged"] = np.where(bt["action_alert"] == 1, np.minimum(bt["potential_stockout_units"], bt["predicted_shortage_units"]), 0)
    bt["unnecessary_order_units_proxy"] = np.where(
        bt["false_positive_alert"] == 1,
        (bt["prediction"] - bt["quantity_sold"]).clip(lower=0),
        0,
    )

    tp = int(bt["true_positive_alert"].sum())
    fp = int(bt["false_positive_alert"].sum())
    fn = int(bt["false_negative_alert"].sum())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    positive_event_windows = int(((bt["actual_spike"] == 1) | (bt["stockout_risk_actual"] == 1)).sum())
    summary = {
        "evaluation_type": "risk_ranking_proxy",
        "primary_use": "Prioritize dealer review, not exact sales or stockout guarantees.",
        "windows_evaluated": int(len(bt)),
        "positive_event_windows": positive_event_windows,
        "alert_windows": int(bt["action_alert"].sum()),
        "true_positive_alerts": tp,
        "false_positive_alerts": fp,
        "false_negative_alerts": fn,
        "alert_precision_percent": round(precision * 100, 2),
        "alert_recall_percent": round(recall * 100, 2),
        "stockout_windows_actual": int(bt["stockout_risk_actual"].sum()),
        "stockout_windows_flagged": int(((bt["action_alert"] == 1) & (bt["stockout_risk_actual"] == 1)).sum()),
        "stockout_units_flagged_proxy": round(float(bt["stockout_units_flagged"].sum()), 2),
        "unnecessary_order_units_proxy": round(float(bt["unnecessary_order_units_proxy"].sum()), 2),
        "interpretation": "Low precision/recall here means the alert heuristic is conservative/noisy on synthetic holdout windows; forecast accuracy is evaluated separately in model_metrics.json.",
        "note": "Backtest proxy pe ferestre de 21 zile: forecastul este folosit ca ranking/risc, nu ca promisiune exacta de vanzari.",
    }
    bt.to_csv(processed_path / "business_alert_backtest_21d.csv", index=False)
    (processed_path / "business_alert_backtest_21d.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, bt


def _write_training_comparison_outputs(processed_path: Path, metrics: Dict[str, object]) -> None:
    out_dir = processed_path / "model_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"model_name": "ExtraTrees global raw", **metrics["raw_global_model_metrics"]},
        {"model_name": "ExtraTrees global + local guard", **metrics["local_guard_model_metrics"]},
        {"model_name": "Final guarded forecast", **metrics["forecast_model_metrics"]},
        {"model_name": "Baseline rolling_mean_28", **metrics["baseline_rolling_mean_28_metrics"]},
    ]
    df = pd.DataFrame(rows).sort_values("WAPE_percent")
    df.to_csv(out_dir / "model_comparison_metrics.csv", index=False)
    (out_dir / "model_comparison_metrics.json").write_text(
        json.dumps(
            {
                "generated_at_utc": _utc_now(),
                "comparison_scope": "same validation window used by train_forecast_model",
                "validation_start_date": metrics["validation_start_date"],
                "validation_end_date": metrics["validation_end_date"],
                "best_model_by_WAPE": df.iloc[0]["model_name"],
                "results": df.to_dict("records"),
            },
            indent=2,
        ),
        encoding="utf-8",
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
    plot_df = df.melt(
        id_vars="model_name",
        value_vars=["MAE", "RMSE", "WAPE_percent", "MAPE_percent"],
        var_name="metric",
        value_name="value",
    )
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, metric in zip(axes.flatten(), ["MAE", "RMSE", "WAPE_percent", "MAPE_percent"]):
        part = plot_df[plot_df["metric"] == metric].sort_values("value")
        colors = ["#2ca02c" if i == 0 else "#1f77b4" for i in range(len(part))]
        ax.barh(part["model_name"], part["value"], color=colors)
        ax.set_title(metric)
        ax.set_xlabel("lower is better")
    fig.suptitle("Forecast training comparison on validation", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_dir / "model_comparison_metrics.png", dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def train_forecast_model(
    raw_dir: str | Path = "data/raw",
    model_dir: str | Path = "models",
    processed_dir: str | Path = "data/processed",
    random_state: int = 42,
    max_train_rows: int = 80000,
    max_final_rows: int = 100000,
) -> Dict[str, object]:
    raw_path = Path(raw_dir)
    model_path = Path(model_dir)
    processed_path = Path(processed_dir)
    model_path.mkdir(parents=True, exist_ok=True)
    processed_path.mkdir(parents=True, exist_ok=True)

    sales = pd.read_csv(raw_path / "sales_history.csv")
    df = prepare_training_frame(sales)
    df["date"] = pd.to_datetime(df["date"])
    max_date = df["date"].max()
    cutoff = max_date - pd.Timedelta(days=90)
    calibration_cutoff = cutoff + pd.Timedelta(days=45)
    train_df = df[df["date"] <= cutoff].copy()
    holdout_df = df[df["date"] > cutoff].copy()
    calib_df = holdout_df[holdout_df["date"] <= calibration_cutoff].copy()
    test_df = holdout_df[holdout_df["date"] > calibration_cutoff].copy()
    train_fit_df = _sample_frame(train_df, max_train_rows, random_state)
    pair_profiles = _build_pair_profiles(train_df)

    X_train = train_fit_df[FEATURE_COLUMNS]
    y_train = train_fit_df[TARGET]
    model = build_model(random_state=random_state)
    model.fit(X_train, y_train)

    sale_model = build_sale_probability_model(random_state=random_state)
    sale_model.fit(X_train, (y_train > 0).astype(int))
    positive_train_df = train_fit_df[train_fit_df[TARGET] > 0].copy()
    if positive_train_df.empty:
        positive_train_df = train_fit_df.copy()
    positive_model = build_positive_quantity_model(random_state=random_state)
    positive_model.fit(positive_train_df[FEATURE_COLUMNS], positive_train_df[TARGET])

    calib_df["raw_prediction"] = np.clip(model.predict(calib_df[FEATURE_COLUMNS]), 0, None)
    calibration = _learn_local_calibration(calib_df)
    calib_eval_frame = calib_df[[
        "date",
        "sku",
        "location_id",
        "category",
        "climate_zone",
        TARGET,
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_mean_28",
        "lag_1",
        "lag_7",
    ]].copy()
    calib_eval_frame["raw_prediction"] = calib_df["raw_prediction"].to_numpy()
    calib_eval_frame["calibrated_prediction"] = apply_local_calibration(calib_eval_frame, calibration).to_numpy()
    sale_prob, conditional_qty, two_stage_pred = _two_stage_predictions(calib_df, sale_model, positive_model)
    calib_eval_frame["sale_probability"] = sale_prob
    calib_eval_frame["conditional_quantity"] = conditional_qty
    calib_eval_frame["two_stage_prediction"] = two_stage_pred
    two_stage_policy = _learn_two_stage_policy(calib_eval_frame, pair_profiles)

    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET]
    raw_pred = np.clip(model.predict(X_test), 0, None)
    eval_frame = test_df[[
        "date",
        "sku",
        "location_id",
        "category",
        "climate_zone",
        TARGET,
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_mean_28",
        "lag_1",
        "lag_7",
    ] + [c for c in ["stockout_flag", "stock_on_hand_end", "weather_spike_flag", "cold_snap_flag", "heatwave_flag"] if c in test_df.columns]].copy()
    eval_frame["raw_prediction"] = raw_pred
    eval_frame["calibrated_prediction"] = apply_local_calibration(eval_frame, calibration).to_numpy()
    sale_prob, conditional_qty, two_stage_pred = _two_stage_predictions(test_df, sale_model, positive_model)
    eval_frame["sale_probability"] = sale_prob
    eval_frame["conditional_quantity"] = conditional_qty
    eval_frame["two_stage_prediction"] = two_stage_pred
    final_pred, prediction_scope = apply_two_stage_policy(eval_frame, two_stage_policy)
    eval_frame["prediction"] = final_pred.to_numpy()
    eval_frame["prediction_scope"] = prediction_scope.to_numpy()
    eval_frame["baseline_prediction"] = np.clip(
        test_df["rolling_mean_28"].fillna(test_df["rolling_mean_14"]).fillna(test_df["rolling_mean_7"]).fillna(y_train.mean()).to_numpy(),
        0,
        None,
    )
    eval_frame = _add_pair_profiles(eval_frame, pair_profiles)

    raw_model_metrics = metrics_dict(y_test, raw_pred)
    raw_model_metrics["R2"] = round(float(r2_score(y_test, raw_pred)), 4)
    local_guard_metrics = metrics_dict(y_test, eval_frame["calibrated_prediction"])
    local_guard_metrics["R2"] = round(float(r2_score(y_test, eval_frame["calibrated_prediction"])), 4)
    two_stage_raw_metrics = metrics_dict(y_test, eval_frame["two_stage_prediction"])
    two_stage_raw_metrics["R2"] = round(float(r2_score(y_test, eval_frame["two_stage_prediction"])), 4)
    model_metrics = metrics_dict(y_test, eval_frame["prediction"])
    model_metrics["R2"] = round(float(r2_score(y_test, eval_frame["prediction"])), 4)

    baseline_pred = eval_frame["baseline_prediction"].to_numpy()
    baseline_metrics = metrics_dict(y_test, baseline_pred)
    baseline_metrics["R2"] = round(float(r2_score(y_test, baseline_pred)), 4)

    by_category = []
    eval_df = eval_frame[["date", "sku", "location_id", "category", "climate_zone", TARGET, "raw_prediction", "calibrated_prediction", "two_stage_prediction", "prediction", "prediction_scope", "baseline_prediction"]].copy()
    for category, group in eval_df.groupby("category"):
        by_category.append({"category": category, **metrics_dict(group[TARGET], group["prediction"]), "n_rows": int(len(group))})
    by_climate = []
    for climate, group in eval_df.groupby("climate_zone"):
        by_climate.append({"climate_zone": climate, **metrics_dict(group[TARGET], group["prediction"]), "n_rows": int(len(group))})
    by_pair = []
    for (sku, location_id), group in eval_df.groupby(["sku", "location_id"]):
        by_pair.append({
            "sku": sku,
            "location_id": location_id,
            "category": group["category"].iloc[0],
            **metrics_dict(group[TARGET], group["prediction"]),
            "raw_WAPE_percent": round(_wape(group[TARGET], group["raw_prediction"]), 4),
            "n_rows": int(len(group)),
        })
    by_pair = sorted(by_pair, key=lambda row: row["WAPE_percent"], reverse=True)
    segmented_daily_metrics, segmented_21d_metrics, holdout_21d = build_segmented_metrics(eval_frame, processed_path)
    business_backtest, _ = build_business_backtest(holdout_21d, processed_path)

    final_fit_df = _sample_frame(df, max_final_rows, random_state)
    final_model = build_model(random_state=random_state)
    final_model.fit(final_fit_df[FEATURE_COLUMNS], final_fit_df[TARGET])
    joblib.dump(final_model, model_path / "demand_forecast_model.joblib")

    final_sale_model = build_sale_probability_model(random_state=random_state)
    final_sale_model.fit(final_fit_df[FEATURE_COLUMNS], (final_fit_df[TARGET] > 0).astype(int))
    final_positive_df = final_fit_df[final_fit_df[TARGET] > 0].copy()
    if final_positive_df.empty:
        final_positive_df = final_fit_df.copy()
    final_positive_model = build_positive_quantity_model(random_state=random_state)
    final_positive_model.fit(final_positive_df[FEATURE_COLUMNS], final_positive_df[TARGET])
    joblib.dump(final_sale_model, model_path / "demand_sale_probability_model.joblib")
    joblib.dump(final_positive_model, model_path / "demand_positive_quantity_model.joblib")

    calibration_payload = {
        "model_scope": "global_model_with_sku_location_local_calibration",
        "trained_at_utc": _utc_now(),
        "calibration_start_date": holdout_df["date"].min().date().isoformat(),
        "calibration_end_date": calibration_cutoff.date().isoformat(),
        "validation_start_date": test_df["date"].min().date().isoformat(),
        "validation_end_date": test_df["date"].max().date().isoformat(),
        "calibration": calibration,
    }
    two_stage_payload = {
        "model_scope": "two_stage_intermittent_demand_guard",
        "trained_at_utc": _utc_now(),
        "policy": two_stage_policy,
        "pair_profiles": pair_profiles.to_dict("records"),
    }
    (model_path / "demand_forecast_calibration.json").write_text(json.dumps(calibration_payload, indent=2), encoding="utf-8")
    (model_path / "demand_two_stage_policy.json").write_text(json.dumps(two_stage_payload, indent=2), encoding="utf-8")
    (processed_path / "demand_forecast_calibration.json").write_text(json.dumps(calibration_payload, indent=2), encoding="utf-8")
    (processed_path / "demand_two_stage_policy.json").write_text(json.dumps(two_stage_payload, indent=2), encoding="utf-8")
    _calibration_rows(calibration).to_csv(processed_path / "demand_forecast_calibration.csv", index=False)
    pair_profiles.to_csv(processed_path / "demand_pair_profiles.csv", index=False)
    two_stage_rows = []
    for key, stats in two_stage_policy.get("by_pair", {}).items():
        sku, location_id = key.split("||", 1)
        two_stage_rows.append({"scope": "sku_location", "sku": sku, "location_id": location_id, **stats})
    for category, stats in two_stage_policy.get("by_category", {}).items():
        two_stage_rows.append({"scope": "category", "category": category, **stats})
    pd.DataFrame(two_stage_rows).to_csv(processed_path / "demand_two_stage_policy.csv", index=False)

    metrics = {
        "model_name": "ExtraTreesRegressor_global_local_two_stage_guard",
        "trained_at_utc": _utc_now(),
        "target": TARGET,
        "holdout_start_date": (cutoff + pd.Timedelta(days=1)).date().isoformat(),
        "holdout_end_date": max_date.date().isoformat(),
        "calibration_end_date": calibration_cutoff.date().isoformat(),
        "validation_start_date": test_df["date"].min().date().isoformat(),
        "validation_end_date": test_df["date"].max().date().isoformat(),
        "full_training_rows_available": int(train_df.shape[0]),
        "rows_used_for_holdout_training": int(train_fit_df.shape[0]),
        "rows_used_for_saved_model": int(final_fit_df.shape[0]),
        "calibration_rows": int(calib_df.shape[0]),
        "validation_rows": int(test_df.shape[0]),
        "holdout_rows": int(holdout_df.shape[0]),
        "features": FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "raw_global_model_metrics": raw_model_metrics,
        "local_guard_model_metrics": local_guard_metrics,
        "two_stage_raw_model_metrics": two_stage_raw_metrics,
        "forecast_model_metrics": model_metrics,
        "baseline_rolling_mean_28_metrics": baseline_metrics,
        "segmented_daily_metrics": segmented_daily_metrics,
        "segmented_21d_metrics": segmented_21d_metrics,
        "business_alert_backtest_21d": business_backtest,
        "metrics_by_category": by_category,
        "metrics_by_climate_zone": by_climate,
        "worst_sku_location_metrics": by_pair[:40],
        "local_calibration": {
            "n_sku_location_calibrators": len(calibration.get("by_pair", {})),
            "n_enabled_sku_location_calibrators": int(sum(1 for s in calibration.get("by_pair", {}).values() if s.get("enabled"))),
            "n_category_calibrators": len(calibration.get("by_category", {})),
            "global_calibrator": calibration.get("global", {}),
        },
        "two_stage_intermittent_model": {
            "n_candidate_pairs": int(pair_profiles["is_two_stage_candidate"].sum()) if not pair_profiles.empty else 0,
            "n_enabled_pair_policies": int(sum(1 for s in two_stage_policy.get("by_pair", {}).values() if s.get("enabled"))),
            "n_enabled_category_policies": int(sum(1 for s in two_stage_policy.get("by_category", {}).values() if s.get("enabled"))),
        },
    }
    (processed_path / "model_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (model_path / "metadata.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _write_training_comparison_outputs(processed_path, metrics)

    sample = eval_df.sample(min(1000, len(eval_df)), random_state=random_state).copy()
    for col in ["raw_prediction", "calibrated_prediction", "two_stage_prediction", "prediction", "baseline_prediction"]:
        sample[col] = sample[col].round(3)
    sample.to_csv(processed_path / "holdout_predictions_sample.csv", index=False)
    return metrics


if __name__ == "__main__":
    result = train_forecast_model()
    print(json.dumps(result["forecast_model_metrics"], indent=2))
