from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CLUSTER_FEATURES = [
    "avg_daily_demand",
    "std_daily_demand",
    "cv_demand",
    "zero_sales_share",
    "stockout_rate",
    "winter_ratio",
    "summer_ratio",
    "payday_uplift",
    "weather_spike_uplift",
    "cold_snap_uplift",
    "heatwave_uplift",
    "promotion_uplift",
    "travel_event_uplift",
    "mean_stock_end",
]


def _safe_ratio(a: float, b: float, default: float = 1.0) -> float:
    if b is None or not np.isfinite(b) or abs(b) < 1e-9:
        return default
    return float(a / b)


def build_segmentation_frame(sales: pd.DataFrame) -> pd.DataFrame:
    df = sales.copy()
    df["date"] = pd.to_datetime(df["date"])
    if "month" not in df.columns:
        df["month"] = df["date"].dt.month
    if "country_code" not in df.columns:
        df["country_code"] = df.get("country", "unknown")
    if "stock_on_hand_end" not in df.columns:
        if "stock_end" in df.columns:
            df["stock_on_hand_end"] = df["stock_end"]
        else:
            df["stock_on_hand_end"] = np.nan
    if "stockout_flag" not in df.columns:
        df["stockout_flag"] = (df["stock_on_hand_end"].fillna(1) <= 0).astype(int)
    if "event_type" not in df.columns:
        df["event_type"] = "none"
    df["is_winter_month"] = df["month"].isin([9, 10, 11, 12, 1, 2, 3]).astype(int)
    df["is_summer_month"] = df["month"].isin([5, 6, 7, 8]).astype(int)
    df["is_travel_event"] = df["event_type"].astype(str).str.contains("holiday_travel|school_holiday", regex=True).astype(int)
    rows: List[Dict[str, object]] = []
    for keys, group in df.groupby(["sku", "location_id", "part_name", "category", "city", "country_code", "climate_zone"]):
        sku, location_id, part_name, category, city, country_code, climate_zone = keys
        qty = group["quantity_sold"].astype(float)
        avg = float(qty.mean())
        std = float(qty.std(ddof=0))
        non_winter = group.loc[group["is_winter_month"] == 0, "quantity_sold"].mean()
        winter = group.loc[group["is_winter_month"] == 1, "quantity_sold"].mean()
        non_summer = group.loc[group["is_summer_month"] == 0, "quantity_sold"].mean()
        summer = group.loc[group["is_summer_month"] == 1, "quantity_sold"].mean()
        non_payday = group.loc[group["is_payday_window"] == 0, "quantity_sold"].mean()
        payday = group.loc[group["is_payday_window"] == 1, "quantity_sold"].mean()
        no_weather_spike = group.loc[group["weather_spike_flag"] == 0, "quantity_sold"].mean()
        weather_spike = group.loc[group["weather_spike_flag"] == 1, "quantity_sold"].mean()
        no_cold = group.loc[group["cold_snap_flag"] == 0, "quantity_sold"].mean()
        cold = group.loc[group["cold_snap_flag"] == 1, "quantity_sold"].mean()
        no_heat = group.loc[group["heatwave_flag"] == 0, "quantity_sold"].mean()
        heat = group.loc[group["heatwave_flag"] == 1, "quantity_sold"].mean()
        no_promo = group.loc[group["promotion_flag"] == 0, "quantity_sold"].mean()
        promo = group.loc[group["promotion_flag"] == 1, "quantity_sold"].mean()
        no_travel = group.loc[group["is_travel_event"] == 0, "quantity_sold"].mean()
        travel = group.loc[group["is_travel_event"] == 1, "quantity_sold"].mean()
        rows.append(
            {
                "sku": sku,
                "location_id": location_id,
                "part_name": part_name,
                "category": category,
                "city": city,
                "country_code": country_code,
                "climate_zone": climate_zone,
                "avg_daily_demand": round(avg, 5),
                "std_daily_demand": round(std, 5),
                "cv_demand": round(_safe_ratio(std, avg, default=0.0), 5),
                "zero_sales_share": round(float((qty == 0).mean()), 5),
                "stockout_rate": round(float(group["stockout_flag"].mean()), 5),
                "winter_ratio": round(_safe_ratio(float(winter), float(non_winter), default=1.0), 5),
                "summer_ratio": round(_safe_ratio(float(summer), float(non_summer), default=1.0), 5),
                "payday_uplift": round(_safe_ratio(float(payday), float(non_payday), default=1.0), 5),
                "weather_spike_uplift": round(_safe_ratio(float(weather_spike), float(no_weather_spike), default=1.0), 5),
                "cold_snap_uplift": round(_safe_ratio(float(cold), float(no_cold), default=1.0), 5),
                "heatwave_uplift": round(_safe_ratio(float(heat), float(no_heat), default=1.0), 5),
                "promotion_uplift": round(_safe_ratio(float(promo), float(no_promo), default=1.0), 5),
                "travel_event_uplift": round(_safe_ratio(float(travel), float(no_travel), default=1.0), 5),
                "mean_stock_end": round(float(group["stock_on_hand_end"].mean()), 5),
            }
        )
    return pd.DataFrame(rows)


def _assign_cluster_names(segments: pd.DataFrame) -> Dict[int, str]:
    profile = segments.groupby("cluster")[CLUSTER_FEATURES].mean()
    assignments: Dict[int, str] = {}
    candidates = [
        ("slow_moving_intermittent", "zero_sales_share"),
        ("winter_weather_sensitive", "cold_snap_uplift"),
        ("summer_heat_sensitive", "heatwave_uplift"),
        ("salary_event_sensitive", "payday_uplift"),
        ("promotion_travel_sensitive", "travel_event_uplift"),
        ("fast_moving_stable", "avg_daily_demand"),
    ]
    used = set()
    for name, feature in candidates:
        ranked = profile[feature].sort_values(ascending=False).index.tolist()
        for cluster_id in ranked:
            if int(cluster_id) not in used:
                assignments[int(cluster_id)] = name
                used.add(int(cluster_id))
                break
    for cluster_id in profile.index:
        assignments.setdefault(int(cluster_id), "balanced_demand")
    return assignments


def train_cluster_model(
    raw_dir: str | Path = "data/raw",
    model_dir: str | Path = "models",
    processed_dir: str | Path = "data/processed",
    n_clusters: int = 6,
    random_state: int = 42,
) -> Dict[str, object]:
    raw_path = Path(raw_dir)
    model_path = Path(model_dir)
    processed_path = Path(processed_dir)
    model_path.mkdir(parents=True, exist_ok=True)
    processed_path.mkdir(parents=True, exist_ok=True)

    sales = pd.read_csv(raw_path / "sales_history.csv")
    segments = build_segmentation_frame(sales)
    X = segments[CLUSTER_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(1.0)
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("kmeans", KMeans(n_clusters=n_clusters, random_state=random_state, n_init=20)),
    ])
    segments["cluster"] = pipeline.fit_predict(X)
    name_map = _assign_cluster_names(segments)
    segments["segment_name"] = segments["cluster"].map(name_map)
    segments["segment_explanation"] = segments["segment_name"].map(
        {
            "slow_moving_intermittent": "Cerere rara, multe zile cu zero vanzari; recomandat safety stock conservator.",
            "winter_weather_sensitive": "Cerere sensibila la frig, zapada si scaderi bruste de temperatura.",
            "summer_heat_sensitive": "Cerere sensibila la caldura si valuri de caldura.",
            "salary_event_sensitive": "Cerere amplificata in zilele de salariu si in ferestrele +/- 1 zi.",
            "promotion_travel_sensitive": "Cerere crescuta la promotii si in ferestrele de calatorii/vacante.",
            "fast_moving_stable": "SKU-locatie cu rulaj mare si cerere relativ stabila.",
            "balanced_demand": "Cerere mixta fara un driver dominant clar.",
        }
    )
    segments.to_csv(processed_path / "segments_kmeans.csv", index=False)
    joblib.dump(pipeline, model_path / "demand_segment_kmeans.joblib")
    metadata = {
        "model_name": "KMeans_SKU_location_segmentation",
        "trained_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "n_clusters": n_clusters,
        "features": CLUSTER_FEATURES,
        "cluster_name_map": {str(k): v for k, v in name_map.items()},
        "n_segmented_pairs": int(segments.shape[0]),
        "segment_counts": segments["segment_name"].value_counts().to_dict(),
    }
    (model_path / "cluster_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (processed_path / "cluster_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    print(json.dumps(train_cluster_model(), indent=2))
