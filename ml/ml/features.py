from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

TARGET = "quantity_sold"
GROUP_COLS = ["sku", "location_id"]

CATEGORICAL_FEATURES = [
    "sku",
    "location_id",
    "country_code",
    "category",
    "seasonality_profile",
    "climate_zone",
    "event_type",
    "season",
]

BASE_NUMERIC_FEATURES = [
    "unit_price_eur",
    "temperature_c",
    "temp_change_1d_c",
    "temp_change_3d_c",
    "abs_temp_change_3d_c",
    "rain_mm",
    "snow_cm",
    "cold_snap_flag",
    "heatwave_flag",
    "weather_spike_flag",
    "temperature_drop_flag",
    "temperature_rise_flag",
    "is_payday",
    "is_payday_window",
    "is_holiday",
    "is_school_holiday",
    "event_multiplier",
    "promotion_flag",
    "service_campaign_flag",
    "fuel_price_eur_l",
    "mobility_index",
    "day_of_week",
    "day_of_month",
    "week_of_year",
    "month",
    "quarter",
    "year",
    "is_weekend",
]

LAG_FEATURES = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",
    "rolling_std_14",
    "rolling_max_28",
    "rolling_min_28",
]

NUMERIC_FEATURES = BASE_NUMERIC_FEATURES + LAG_FEATURES
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.date
    return result


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    dt = pd.to_datetime(result["date"])
    result["day_of_week"] = dt.dt.dayofweek
    result["day_of_month"] = dt.dt.day
    result["week_of_year"] = dt.dt.isocalendar().week.astype(int)
    result["month"] = dt.dt.month
    result["quarter"] = dt.dt.quarter
    result["year"] = dt.dt.year
    result["is_weekend"] = result["day_of_week"].isin([5, 6]).astype(int)
    result["season"] = np.select(
        [result["month"].isin([12, 1, 2]), result["month"].isin([3, 4, 5]), result["month"].isin([6, 7, 8])],
        ["winter", "spring", "summer"],
        default="autumn",
    )
    return result


def add_lag_features(df: pd.DataFrame, target_col: str = TARGET) -> pd.DataFrame:
    result = df.copy()
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values(GROUP_COLS + ["date"]).reset_index(drop=True)
    group = result.groupby(GROUP_COLS, sort=False)[target_col]
    for lag in [1, 7, 14, 28]:
        result[f"lag_{lag}"] = group.shift(lag)
    shifted = group.shift(1)
    result["rolling_mean_7"] = shifted.groupby([result["sku"], result["location_id"]]).rolling(7, min_periods=2).mean().reset_index(level=[0, 1], drop=True)
    result["rolling_mean_14"] = shifted.groupby([result["sku"], result["location_id"]]).rolling(14, min_periods=3).mean().reset_index(level=[0, 1], drop=True)
    result["rolling_mean_28"] = shifted.groupby([result["sku"], result["location_id"]]).rolling(28, min_periods=7).mean().reset_index(level=[0, 1], drop=True)
    result["rolling_std_14"] = shifted.groupby([result["sku"], result["location_id"]]).rolling(14, min_periods=3).std().reset_index(level=[0, 1], drop=True)
    result["rolling_max_28"] = shifted.groupby([result["sku"], result["location_id"]]).rolling(28, min_periods=7).max().reset_index(level=[0, 1], drop=True)
    result["rolling_min_28"] = shifted.groupby([result["sku"], result["location_id"]]).rolling(28, min_periods=7).min().reset_index(level=[0, 1], drop=True)
    return result


def prepare_training_frame(sales_df: pd.DataFrame) -> pd.DataFrame:
    df = sales_df.copy()
    df = add_time_features(df)
    df = add_lag_features(df)
    for col in CATEGORICAL_FEATURES:
        if col not in df.columns:
            df[col] = "unknown"
        df[col] = df[col].fillna("unknown").astype(str)
    for col in NUMERIC_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=LAG_FEATURES + [TARGET]).reset_index(drop=True)
    return df


def training_columns() -> Tuple[List[str], List[str], List[str]]:
    return FEATURE_COLUMNS.copy(), CATEGORICAL_FEATURES.copy(), NUMERIC_FEATURES.copy()


def metrics_dict(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mask = y_true > 0
    mape = float(np.mean(np.abs(err[mask] / y_true[mask])) * 100) if mask.any() else 0.0
    wape = float(np.sum(np.abs(err)) / max(1e-9, np.sum(np.abs(y_true))) * 100)
    bias = float(np.mean(y_pred - y_true))
    return {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "MAPE_percent": round(mape, 4),
        "WAPE_percent": round(wape, 4),
        "bias_units": round(bias, 4),
    }
