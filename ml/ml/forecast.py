from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd

from ml.data_generator import LOCATIONS, _fuel_price, _mobility_index
from ml.features import CATEGORICAL_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES, add_time_features


def _lag_values(history: List[float]) -> Dict[str, float]:
    arr = np.asarray(history, dtype=float)
    fallback = float(arr.mean()) if len(arr) else 0.0
    def lag(n: int) -> float:
        return float(arr[-n]) if len(arr) >= n else fallback
    def roll(n: int, fn, default: float = 0.0) -> float:
        if len(arr) == 0:
            return default
        window = arr[-min(n, len(arr)):]
        return float(fn(window))
    return {
        "lag_1": lag(1),
        "lag_7": lag(7),
        "lag_14": lag(14),
        "lag_28": lag(28),
        "rolling_mean_7": roll(7, np.mean),
        "rolling_mean_14": roll(14, np.mean),
        "rolling_mean_28": roll(28, np.mean),
        "rolling_std_14": roll(14, np.std),
        "rolling_max_28": roll(28, np.max),
        "rolling_min_28": roll(28, np.min),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pair_key(sku: str, location_id: str) -> str:
    return f"{sku}||{location_id}"


def _load_calibration(model_path: Path, processed_path: Path) -> Dict[str, object]:
    for path in [model_path / "demand_forecast_calibration.json", processed_path / "demand_forecast_calibration.json"]:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("calibration", {})
    return {}


def _load_two_stage_policy(model_path: Path, processed_path: Path) -> Dict[str, object]:
    for path in [model_path / "demand_two_stage_policy.json", processed_path / "demand_two_stage_policy.json"]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")).get("policy", {})
    return {}


def _load_optional_model(path: Path):
    return joblib.load(path) if path.exists() else None


def _candidate_baseline(row: pd.Series) -> float:
    for col in ["rolling_mean_28", "rolling_mean_14", "rolling_mean_7", "lag_7", "lag_1"]:
        value = row.get(col)
        if pd.notna(value):
            return max(0.0, float(value))
    return 0.0


def _calibrate_prediction(row: pd.Series, raw_prediction: float, calibration: Dict[str, object]) -> tuple[float, str, float, float]:
    if not calibration:
        return max(0.0, float(raw_prediction)), "global_raw", 1.0, 1.0
    key = _pair_key(str(row["sku"]), str(row["location_id"]))
    by_pair = calibration.get("by_pair", {})
    by_category = calibration.get("by_category", {})
    scope = "sku_location"
    stats = by_pair.get(key)
    if stats is None:
        stats = by_category.get(str(row.get("category", "")))
        scope = "category"
    if stats is None:
        stats = calibration.get("global", {})
        scope = "global"
    if stats and not bool(stats.get("enabled", True)):
        return max(0.0, float(raw_prediction)), f"{scope}_raw_fallback", 1.0, 1.0
    weight = float(stats.get("global_weight", 1.0))
    scale = float(stats.get("scale_factor", 1.0))
    baseline = _candidate_baseline(row)
    pred = (weight * max(0.0, float(raw_prediction)) + (1.0 - weight) * baseline) * scale
    return max(0.0, float(pred)), scope, weight, scale


def _predict_sale_probability(model, frame: pd.DataFrame) -> np.ndarray:
    if model is None:
        return np.zeros(len(frame))
    proba = model.predict_proba(frame[FEATURE_COLUMNS])
    classes = list(model.named_steps["model"].classes_)
    if 1 in classes:
        return np.clip(proba[:, classes.index(1)], 0, 1)
    return np.clip(proba[:, -1], 0, 1)


def _two_stage_predictions(sale_model, positive_model, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if sale_model is None or positive_model is None:
        zeros = np.zeros(len(frame))
        return zeros, zeros, zeros
    sale_probability = _predict_sale_probability(sale_model, frame)
    conditional_quantity = np.clip(positive_model.predict(frame[FEATURE_COLUMNS]), 0, None)
    two_stage_prediction = sale_probability * conditional_quantity
    return sale_probability, conditional_quantity, two_stage_prediction


def _apply_two_stage_policy(
    row: pd.Series,
    local_prediction: float,
    two_stage_prediction: float,
    local_scope: str,
    policy: Dict[str, object],
) -> tuple[float, str]:
    if not policy:
        return local_prediction, local_scope
    key = _pair_key(str(row["sku"]), str(row["location_id"]))
    stats = policy.get("by_pair", {}).get(key)
    if stats is not None and stats.get("enabled", False):
        return max(0.0, float(two_stage_prediction)), "two_stage_sku_location"
    stats = policy.get("by_category", {}).get(str(row.get("category", "")))
    if stats is not None and stats.get("enabled", False):
        return max(0.0, float(two_stage_prediction)), "two_stage_category"
    return local_prediction, local_scope


def _normalize_inputs(parts: pd.DataFrame, locations: pd.DataFrame, weather: pd.DataFrame, calendar: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = parts.copy()
    locations = locations.copy()
    weather = weather.copy()
    calendar = calendar.copy()

    if "seasonality_profile" not in parts.columns:
        parts["seasonality_profile"] = "unknown"
    if "country_code" not in locations.columns:
        locations["country_code"] = locations.get("country", "unknown")

    for frame in [weather, calendar]:
        frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)

    for col in ["rain_mm", "snow_cm", "temperature_c"]:
        if col not in weather.columns:
            weather[col] = 0.0
    for col in ["temp_change_1d_c", "temp_change_3d_c", "abs_temp_change_3d_c"]:
        if col not in weather.columns:
            weather[col] = 0.0
    for col in ["cold_snap_flag", "heatwave_flag", "weather_spike_flag", "temperature_drop_flag", "temperature_rise_flag"]:
        if col not in weather.columns:
            weather[col] = 0

    for col in ["is_payday", "is_payday_window", "is_holiday", "is_school_holiday", "promotion_flag", "service_campaign_flag"]:
        if col not in calendar.columns:
            calendar[col] = 0
    if "event_type" not in calendar.columns:
        calendar["event_type"] = "none"
    if "event_multiplier" not in calendar.columns:
        calendar["event_multiplier"] = 1.0

    return parts, locations, weather, calendar


def _weather_phase(loc_id: str) -> float:
    return float(sum((idx + 1) * ord(ch) for idx, ch in enumerate(str(loc_id))) % 31)


def _same_season_weather_source(loc_history: pd.DataFrame, d) -> pd.DataFrame:
    if loc_history.empty:
        return loc_history
    day_of_year = int(pd.Timestamp(d).dayofyear)
    history_doy = loc_history["date_dt"].dt.dayofyear.astype(int)
    distance = (history_doy - day_of_year).abs()
    circular_distance = np.minimum(distance, 366 - distance)
    source = loc_history.loc[circular_distance <= 7]
    return source if not source.empty else loc_history.loc[loc_history["date_dt"].dt.month == d.month]


def _fallback_weather_row(d, loc_id: str, history: pd.DataFrame, loc_profile_by_id: Dict[str, object]) -> Dict[str, object]:
    loc_history = history.loc[history["location_id"] == loc_id].copy()
    loc_history["date_dt"] = pd.to_datetime(loc_history["date"])
    source = _same_season_weather_source(loc_history, d)
    profile = loc_profile_by_id.get(loc_id)

    if not source.empty:
        base_temp = float(source["temperature_c"].mean())
        temp_std = float(source["temperature_c"].std(ddof=0))
        rain_base = float(source["rain_mm"].mean()) if "rain_mm" in source.columns else 0.0
        snow_base = float(source["snow_cm"].mean()) if "snow_cm" in source.columns else 0.0
    elif profile is not None:
        day_angle = 2 * math.pi * (pd.Timestamp(d).dayofyear - 15) / 365.25
        base_temp = float(profile.temp_mean_c - profile.temp_amplitude_c * math.cos(day_angle))
        temp_std = 2.0
        rain_base = 1.0
        snow_base = 0.0
    else:
        base_temp = 10.0
        temp_std = 2.0
        rain_base = 1.0
        snow_base = 0.0

    phase = _weather_phase(loc_id)
    day = float(pd.Timestamp(d).dayofyear)
    synoptic_wave = math.sin(2 * math.pi * (day + phase) / 9.0)
    slower_wave = math.sin(2 * math.pi * (day + phase * 0.7) / 17.0)
    daily_variation = (max(1.2, min(4.0, temp_std)) * 0.75 * synoptic_wave) + (0.9 * slower_wave)

    previous = loc_history.sort_values("date_dt").tail(3)["temperature_c"].astype(float).tolist()
    previous_1d = previous[-1] if previous else base_temp
    target_temp = base_temp + daily_variation
    temp = 0.58 * target_temp + 0.42 * previous_1d
    previous_3d = previous[0] if len(previous) >= 3 else previous_1d
    change_1d = temp - previous_1d
    change_3d = temp - previous_3d
    abs_change_3d = abs(change_3d)

    moisture_wave = max(0.0, math.sin(2 * math.pi * (day + phase * 1.3) / 6.0))
    rain = max(0.0, rain_base * (0.65 + 0.7 * moisture_wave))
    snow = max(0.0, snow_base * (0.55 + 0.9 * moisture_wave)) if temp <= 1.5 else 0.0
    return {
        "date": d.isoformat(),
        "location_id": loc_id,
        "temperature_c": round(temp, 2),
        "rain_mm": round(max(0.0, rain), 2),
        "snow_cm": round(max(0.0, snow), 2),
        "temp_change_1d_c": round(change_1d, 2),
        "temp_change_3d_c": round(change_3d, 2),
        "abs_temp_change_3d_c": round(abs_change_3d, 2),
        "cold_snap_flag": int(temp <= -5 or change_3d <= -6),
        "heatwave_flag": int(temp >= 30 or change_3d >= 6),
        "weather_spike_flag": int(abs_change_3d >= 5),
        "temperature_drop_flag": int(change_3d <= -5),
        "temperature_rise_flag": int(change_3d >= 5),
        "fuel_price_eur_l": _fuel_price(d, profile) if profile is not None else 1.7,
        "mobility_index": _mobility_index(d),
    }


def _extend_weather_if_needed(weather: pd.DataFrame, locations: pd.DataFrame, future_dates, loc_profile_by_id: Dict[str, object]) -> pd.DataFrame:
    existing_keys = set(zip(weather["date"].astype(str), weather["location_id"].astype(str)))
    extra_rows: List[Dict[str, object]] = []
    working = weather.copy()
    for d in future_dates:
        for loc_id in locations["location_id"].astype(str):
            key = (d.isoformat(), loc_id)
            if key in existing_keys:
                continue
            row = _fallback_weather_row(d, loc_id, working, loc_profile_by_id)
            extra_rows.append(row)
            working = pd.concat([working, pd.DataFrame([row])], ignore_index=True)
            existing_keys.add(key)
    if extra_rows:
        weather = pd.concat([weather, pd.DataFrame(extra_rows)], ignore_index=True)
    return weather


def _fallback_calendar_row(d, loc_profile=None) -> Dict[str, object]:
    salary_days = set(getattr(loc_profile, "salary_days", (25,)))
    is_payday = int(d.day in salary_days)
    is_payday_window = int(any(abs(d.day - day) <= 1 for day in salary_days))
    return {
        "date": d.isoformat(),
        "is_payday": is_payday,
        "is_payday_window": is_payday_window,
        "is_holiday": 0,
        "is_school_holiday": 0,
        "event_type": "none",
        "event_multiplier": 1.0,
        "promotion_flag": 0,
        "service_campaign_flag": 0,
    }


def _calendar_lookup(calendar: pd.DataFrame) -> Dict[tuple, Dict[str, object]]:
    lookup: Dict[tuple, Dict[str, object]] = {}
    has_location = "location_id" in calendar.columns
    for _, row in calendar.iterrows():
        key = (str(row["date"]), str(row["location_id"]) if has_location else None)
        lookup[key] = row.to_dict()
    return lookup


def run_forecast(
    raw_dir: str | Path = "data/raw",
    model_dir: str | Path = "models",
    processed_dir: str | Path = "data/processed",
    horizon: int = 30,
) -> pd.DataFrame:
    raw_path = Path(raw_dir)
    model_path = Path(model_dir)
    processed_path = Path(processed_dir)
    processed_path.mkdir(parents=True, exist_ok=True)

    model = joblib.load(model_path / "demand_forecast_model.joblib")
    calibration = _load_calibration(model_path, processed_path)
    two_stage_policy = _load_two_stage_policy(model_path, processed_path)
    sale_model = _load_optional_model(model_path / "demand_sale_probability_model.joblib")
    positive_model = _load_optional_model(model_path / "demand_positive_quantity_model.joblib")
    sales = pd.read_csv(raw_path / "sales_history.csv")
    parts = pd.read_csv(raw_path / "parts_master.csv")
    locations = pd.read_csv(raw_path / "eu_locations.csv")
    weather = pd.read_csv(raw_path / "weather_daily.csv")
    calendar = pd.read_csv(raw_path / "calendar_daily.csv")
    loc_profile_by_id = {loc.location_id: loc for loc in LOCATIONS}
    parts, locations, weather, calendar = _normalize_inputs(parts, locations, weather, calendar)
    segments_path = processed_path / "segments_kmeans.csv"
    segments = pd.read_csv(segments_path) if segments_path.exists() else pd.DataFrame()

    sales["date"] = pd.to_datetime(sales["date"])
    last_date = sales["date"].max().date()
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon, freq="D").date
    weather = _extend_weather_if_needed(weather, locations, future_dates, loc_profile_by_id)

    weather_idx = weather.set_index(["date", "location_id"])
    calendar_by_key = _calendar_lookup(calendar)
    loc_records = locations.to_dict(orient="records")
    part_records = parts.to_dict(orient="records")
    part_by_sku = {p["sku"]: p for p in part_records}
    loc_by_id = {l["location_id"]: l for l in loc_records}
    history: Dict[Tuple[str, str], List[float]] = {}
    for (sku, loc_id), group in sales.sort_values("date").groupby(["sku", "location_id"]):
        history[(sku, loc_id)] = group["quantity_sold"].astype(float).tolist()

    segment_lookup = {}
    if not segments.empty:
        for _, row in segments.iterrows():
            segment_lookup[(row["sku"], row["location_id"])] = (row.get("segment_name", "unknown"), row.get("cluster", -1))

    forecast_rows: List[Dict[str, object]] = []
    generated_at = _utc_now()
    for horizon_day, d in enumerate(future_dates, start=1):
        batch_rows: List[Dict[str, object]] = []
        keys: List[Tuple[str, str]] = []
        for loc in loc_records:
            loc_id = loc["location_id"]
            w = weather_idx.loc[(d.isoformat(), loc_id)]
            cal = calendar_by_key.get((d.isoformat(), str(loc_id)))
            if cal is None:
                cal = calendar_by_key.get((d.isoformat(), None))
            if cal is None:
                cal = _fallback_calendar_row(d, loc_profile_by_id.get(loc_id))
            for part in part_records:
                key = (part["sku"], loc_id)
                history.setdefault(key, [])
                lags = _lag_values(history[key])
                row = {
                    "date": d.isoformat(),
                    "sku": part["sku"],
                    "location_id": loc_id,
                    "country_code": loc["country_code"],
                    "category": part["category"],
                    "seasonality_profile": part["seasonality_profile"],
                    "climate_zone": loc["climate_zone"],
                    "event_type": cal["event_type"],
                    "unit_price_eur": float(part["unit_price_eur"]),
                    "temperature_c": float(w["temperature_c"]),
                    "temp_change_1d_c": float(w["temp_change_1d_c"]),
                    "temp_change_3d_c": float(w["temp_change_3d_c"]),
                    "abs_temp_change_3d_c": float(w["abs_temp_change_3d_c"]),
                    "rain_mm": float(w["rain_mm"]),
                    "snow_cm": float(w["snow_cm"]),
                    "cold_snap_flag": int(w["cold_snap_flag"]),
                    "heatwave_flag": int(w["heatwave_flag"]),
                    "weather_spike_flag": int(w["weather_spike_flag"]),
                    "temperature_drop_flag": int(w["temperature_drop_flag"]),
                    "temperature_rise_flag": int(w["temperature_rise_flag"]),
                    "is_payday": int(cal["is_payday"]),
                    "is_payday_window": int(cal["is_payday_window"]),
                    "is_holiday": int(cal["is_holiday"]),
                    "is_school_holiday": int(cal["is_school_holiday"]),
                    "event_multiplier": float(cal["event_multiplier"]),
                    "promotion_flag": int(cal["promotion_flag"]),
                    "service_campaign_flag": int(cal["service_campaign_flag"]),
                    "fuel_price_eur_l": _fuel_price(d, loc_profile_by_id[loc_id]),
                    "mobility_index": _mobility_index(d),
                    **lags,
                }
                batch_rows.append(row)
                keys.append(key)
        batch = pd.DataFrame(batch_rows)
        batch = add_time_features(batch)
        for col in CATEGORICAL_FEATURES:
            batch[col] = batch[col].fillna("unknown").astype(str)
        for col in NUMERIC_FEATURES:
            if col not in batch.columns:
                batch[col] = 0.0
            batch[col] = pd.to_numeric(batch[col], errors="coerce").fillna(0.0)
        raw_predictions = np.clip(model.predict(batch[FEATURE_COLUMNS]), 0, None)
        sale_probability, conditional_quantity, two_stage_predictions = _two_stage_predictions(sale_model, positive_model, batch)
        for idx, raw_pred in enumerate(raw_predictions):
            key = keys[idx]
            row = batch_rows[idx]
            feature_row = batch.iloc[idx]
            part = part_by_sku[key[0]]
            loc = loc_by_id[key[1]]
            seg_name, cluster_id = segment_lookup.get(key, ("unknown", -1))
            local_pred, calibration_scope, calibration_weight, calibration_scale = _calibrate_prediction(feature_row, float(raw_pred), calibration)
            pred_value, prediction_scope = _apply_two_stage_policy(
                feature_row,
                local_pred,
                float(two_stage_predictions[idx]),
                calibration_scope,
                two_stage_policy,
            )
            history[key].append(pred_value)
            forecast_rows.append(
                {
                    "forecast_generated_at_utc": generated_at,
                    "forecast_date": d.isoformat(),
                    "horizon_day": horizon_day,
                    "timestamp": row["date"] + "T18:00:00",
                    "sku": key[0],
                    "part_name": part["part_name"],
                    "category": part["category"],
                    "seasonality_profile": part["seasonality_profile"],
                    "location_id": key[1],
                    "city": loc["city"],
                    "country_code": loc["country_code"],
                    "climate_zone": loc["climate_zone"],
                    "predicted_quantity": round(pred_value, 4),
                    "raw_predicted_quantity": round(float(raw_pred), 4),
                    "local_guard_prediction": round(float(local_pred), 4),
                    "sale_probability": round(float(sale_probability[idx]), 4),
                    "conditional_quantity_if_sale": round(float(conditional_quantity[idx]), 4),
                    "two_stage_predicted_quantity": round(float(two_stage_predictions[idx]), 4),
                    "prediction_scope": prediction_scope,
                    "local_calibration_weight": round(calibration_weight, 4),
                    "local_calibration_scale": round(calibration_scale, 4),
                    "predicted_revenue_eur": round(pred_value * float(part["unit_price_eur"]), 2),
                    "temperature_c": row["temperature_c"],
                    "temp_change_3d_c": row["temp_change_3d_c"],
                    "rain_mm": row["rain_mm"],
                    "snow_cm": row["snow_cm"],
                    "weather_spike_flag": row["weather_spike_flag"],
                    "cold_snap_flag": row["cold_snap_flag"],
                    "heatwave_flag": row["heatwave_flag"],
                    "is_payday_window": row["is_payday_window"],
                    "event_type": row["event_type"],
                    "event_multiplier": row["event_multiplier"],
                    "segment_name": seg_name,
                    "cluster": int(cluster_id) if str(cluster_id) != "nan" else -1,
                }
            )
    forecast_df = pd.DataFrame(forecast_rows)
    csv_path = processed_path / f"forecast_{horizon}d.csv"
    json_path = processed_path / f"forecast_{horizon}d.json"
    forecast_df.to_csv(csv_path, index=False)
    json_path.write_text(forecast_df.head(5000).to_json(orient="records", indent=2), encoding="utf-8")
    return forecast_df


if __name__ == "__main__":
    df = run_forecast()
    print(json.dumps({"rows": int(df.shape[0]), "date_min": df["forecast_date"].min(), "date_max": df["forecast_date"].max()}, indent=2))
