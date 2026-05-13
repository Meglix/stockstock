from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable

import numpy as np
import pandas as pd
import plotly.express as px

DEFAULT_HORIZON = 21
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
TRIGGER_LABELS = {
    "cold_snap_flag": "cold snap",
    "heatwave_flag": "heatwave",
    "weather_spike_flag": "weather spike",
    "temperature_drop_flag": "temperature drop",
    "temperature_rise_flag": "temperature rise",
    "is_payday_window": "payday window",
    "promotion_flag": "promotion",
    "service_campaign_flag": "service campaign",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    cleaned = df.replace({np.nan: None})
    return json.loads(cleaned.to_json(orient="records"))


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    existing = set(columns)
    for col in candidates:
        if col in existing:
            return col
    return None


def _series(frame: pd.DataFrame, column: str, default=0):
    if column in frame.columns:
        return frame[column]
    return pd.Series(default, index=frame.index)


def normalize_locations(locations: pd.DataFrame) -> pd.DataFrame:
    rows = locations.copy()
    if "country_code" not in rows.columns:
        rows["country_code"] = rows.get("country", "unknown")
    if "latitude" not in rows.columns:
        rows["latitude"] = _series(rows, "lat", np.nan)
    if "longitude" not in rows.columns:
        rows["longitude"] = _series(rows, "lon", np.nan)
    return rows


def supplier_for_category(category: str, default_supplier: str) -> str:
    category_map = {
        "winter_fluids": "SUP-FLUIDS-EU",
        "summer_fluids": "SUP-FLUIDS-EU",
        "coolant": "SUP-FLUIDS-EU",
        "consumables": "SUP-FLUIDS-EU",
        "wipers": "SUP-ACCESS-EU",
        "accessories": "SUP-ACCESS-EU",
        "battery": "SUP-ELECTRIC-DE",
        "lighting": "SUP-ELECTRIC-DE",
        "filters": "SUP-FILTERS-FR",
        "maintenance": "SUP-MAINT-DE",
        "brakes": "SUP-BRAKES-IT",
        "ac_cooling": "SUP-CLIMATE-ES",
        "tires": "SUP-TIRES-PL",
    }
    return category_map.get(str(category), default_supplier)


def normalize_inventory(raw_dir: Path, inventory: pd.DataFrame) -> pd.DataFrame:
    stock = inventory.copy()
    parts = _read_csv(raw_dir / "parts_master.csv")
    part_cols = [col for col in ["sku", "lead_time_days", "safety_stock_units", "min_order_qty", "supplier_id"] if col in parts.columns]
    if part_cols and part_cols != ["sku"]:
        stock = stock.merge(parts[part_cols], on="sku", how="left", suffixes=("", "_part"))
    stock["current_stock"] = pd.to_numeric(_series(stock, "current_stock", _series(stock, "current_stock_units", 0)), errors="coerce").fillna(0)
    stock["safety_stock"] = pd.to_numeric(_series(stock, "safety_stock", _series(stock, "safety_stock_units", _series(stock, "reorder_point", 0))), errors="coerce").fillna(0)
    if "lead_time_days_part" in stock.columns:
        stock["lead_time_days"] = pd.to_numeric(_series(stock, "lead_time_days"), errors="coerce").fillna(pd.to_numeric(stock["lead_time_days_part"], errors="coerce"))
    stock["lead_time_days"] = pd.to_numeric(_series(stock, "lead_time_days", 7), errors="coerce").fillna(7)
    stock["min_order_qty"] = pd.to_numeric(_series(stock, "min_order_qty", _series(stock, "reorder_point", stock["safety_stock"])), errors="coerce").fillna(1).clip(lower=1)
    stock["optimal_stock"] = pd.to_numeric(
        _series(stock, "optimal_stock", _series(stock, "reorder_point", 0) + stock["safety_stock"]),
        errors="coerce",
    ).fillna(stock["safety_stock"])
    stock["pending_order_qty"] = pd.to_numeric(_series(stock, "pending_order_qty", 0), errors="coerce").fillna(0)
    return stock


def safe_div(num, den):
    return num / (den + 1e-6)


def priority_rank(series: pd.Series) -> pd.Series:
    return series.map(PRIORITY_ORDER).fillna(9).astype(int)


def ensure_product_location_scores(raw_dir: Path, processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / "sales_intelligence" / "product_location_scores.csv"
    scores = _read_csv(path)
    if not scores.empty:
        return scores

    sales = _read_csv(raw_dir / "sales_history.csv", parse_dates=["date"])
    if sales.empty:
        return pd.DataFrame()
    sales["month"] = sales["date"].dt.month
    rows = []
    for (sku, location_id), group in sales.groupby(["sku", "location_id"], sort=False):
        monthly = group.groupby("month")["quantity_sold"].mean().reindex(range(1, 13), fill_value=0)
        daily = group.groupby("date")["quantity_sold"].sum()
        avg_daily = float(daily.mean())
        rows.append(
            {
                "sku": sku,
                "location_id": location_id,
                "part_name": group["part_name"].iloc[0],
                "category": group["category"].iloc[0],
                "city": group["city"].iloc[0],
                "country_code": group["country_code"].iloc[0],
                "climate_zone": group["climate_zone"].iloc[0],
                "avg_daily_sales": round(avg_daily, 4),
                "volatility_score": round(float(safe_div(daily.std(ddof=0), avg_daily)), 4),
                "seasonality_score": round(float(safe_div(monthly.max() - monthly.min(), monthly.mean())), 4),
                "weather_sensitivity_score": round(float(group.get("weather_spike_applied", pd.Series([0])).mean()), 4),
                "peak_month": int(monthly.idxmax()),
            }
        )
    scores = pd.DataFrame(rows)
    if not scores.empty:
        scores["business_impact_score"] = (
            scores["volatility_score"].rank(pct=True) * 35
            + scores["seasonality_score"].rank(pct=True) * 35
            + scores["avg_daily_sales"].rank(pct=True) * 30
        ).round(2)
    return scores


def ensure_forecast_summary(raw_dir: Path, processed_dir: Path, horizon: int) -> pd.DataFrame:
    path = processed_dir / "sales_intelligence" / "forecast_21d_summary.csv"
    summary = _read_csv(path)
    if not summary.empty:
        return summary

    forecast = _read_csv(processed_dir / "forecast_30d.csv", parse_dates=["forecast_date"])
    sales = _read_csv(raw_dir / "sales_history.csv", parse_dates=["date"])
    if forecast.empty:
        return pd.DataFrame()
    pred_col = first_existing(forecast.columns, ["predicted_quantity", "forecast_quantity", "prediction", "yhat"])
    if pred_col is None:
        return pd.DataFrame()
    if "horizon_day" in forecast.columns:
        fc = forecast[forecast["horizon_day"] <= horizon].copy()
    else:
        fc = forecast.sort_values("forecast_date").groupby(["sku", "location_id"]).head(horizon).copy()

    for col in ["rain_mm", "snow_cm", "cold_snap_flag", "heatwave_flag", "weather_spike_flag", "is_payday_window"]:
        if col not in fc.columns:
            fc[col] = 0

    summary = (
        fc.groupby(["sku", "location_id"], as_index=False)
        .agg(
            part_name=("part_name", "first"),
            category=("category", "first"),
            city=("city", "first"),
            country_code=("country_code", "first"),
            climate_zone=("climate_zone", "first"),
            forecast_21d_units=(pred_col, "sum"),
            forecast_avg_daily=(pred_col, "mean"),
            forecast_peak_day_units=(pred_col, "max"),
            rain_days=("rain_mm", lambda s: int((s >= 4).sum())),
            snow_days=("snow_cm", lambda s: int((s > 0).sum())),
            cold_snap_days=("cold_snap_flag", "sum"),
            heatwave_days=("heatwave_flag", "sum"),
            weather_spike_days=("weather_spike_flag", "sum"),
            payday_window_days=("is_payday_window", "sum"),
        )
    )
    if not sales.empty:
        baseline = (
            sales.sort_values(["sku", "location_id", "date"])
            .groupby(["sku", "location_id"], sort=False)
            .tail(56)
            .groupby(["sku", "location_id"], as_index=False)["quantity_sold"]
            .mean()
            .rename(columns={"quantity_sold": "baseline_avg_daily"})
        )
        summary = summary.merge(baseline, on=["sku", "location_id"], how="left")
    else:
        summary["baseline_avg_daily"] = np.nan
    summary["baseline_21d_units"] = summary["baseline_avg_daily"].fillna(0) * horizon
    summary["uplift_vs_baseline_percent"] = (
        safe_div(summary["forecast_21d_units"] - summary["baseline_21d_units"], summary["baseline_21d_units"]) * 100
    ).round(2)
    return summary


def build_dealer_alert_center(processed_dir: Path, forecast_summary: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    alerts_path = processed_dir / "sales_intelligence" / "weather_sales_alerts_21d.csv"
    weather_alerts = _read_csv(alerts_path)
    if not forecast_summary.empty:
        candidates = forecast_summary.copy()
        for col in ["weather_sensitivity_score", "seasonality_score", "business_impact_score"]:
            if col not in candidates.columns:
                candidates[col] = 0.0
        if "business_trigger_days" in candidates.columns:
            candidates["trigger_days"] = candidates["business_trigger_days"].fillna(0).clip(lower=0, upper=21)
        else:
            weather_cols = [c for c in ["rain_days", "snow_days", "cold_snap_days", "heatwave_days", "weather_spike_days", "payday_window_days"] if c in candidates.columns]
            candidates["trigger_days"] = candidates[weather_cols].fillna(0).max(axis=1).clip(lower=0, upper=21) if weather_cols else 0
        candidates["forecast_risk_score"] = (
            candidates["uplift_vs_baseline_percent"].fillna(0).clip(lower=0, upper=120) * 0.35
            + np.log1p(candidates["forecast_21d_units"].fillna(0)) * 9
            + candidates["trigger_days"].clip(upper=10) * 3
            + candidates["weather_sensitivity_score"].fillna(0).clip(upper=3) * 8
            + candidates["seasonality_score"].fillna(0).clip(upper=3) * 4
        ).round(2)
        min_score = max(35.0, float(candidates["forecast_risk_score"].quantile(0.70)))
        candidates = candidates[
            (candidates["forecast_risk_score"] >= min_score)
            & (candidates["forecast_21d_units"].fillna(0) >= 5)
            & (candidates["uplift_vs_baseline_percent"].fillna(0) >= 5)
        ].copy()
        if not candidates.empty:
            candidates["priority"] = np.select(
                [candidates["uplift_vs_baseline_percent"] >= 30, candidates["uplift_vs_baseline_percent"] >= 12, candidates["uplift_vs_baseline_percent"] >= 5],
                ["critical", "high", "medium"],
                default="low",
            )
            candidates["alert_reason"] = (
                "ranked demand spike signal: uplift "
                + candidates["uplift_vs_baseline_percent"].round(0).astype(int).astype(str)
                + "%, trigger days "
                + candidates["trigger_days"].round(0).astype(int).astype(str)
            )
            candidates["alert_type"] = np.where(candidates["trigger_days"].fillna(0) > 0, "weather_demand_spike", "demand_spike")
            candidates["dealer_message"] = (
                candidates["city"].astype(str)
                + ": spike estimat la "
                + candidates["part_name"].astype(str)
                + ". Forecast 21 zile: "
                + candidates["forecast_21d_units"].round(0).astype(int).astype(str)
                + " buc; uplift "
                + candidates["uplift_vs_baseline_percent"].round(0).astype(int).astype(str)
                + "% vs baseline."
            )
            keep = [
                "location_id",
                "city",
                "country_code",
                "sku",
                "part_name",
                "category",
                "forecast_21d_units",
                "baseline_21d_units",
                "uplift_vs_baseline_percent",
                "trigger_days",
                "alert_type",
                "priority",
                "alert_reason",
                "dealer_message",
                "weather_sensitivity_score",
                "seasonality_score",
                "forecast_risk_score",
            ]
            ranked_alerts = candidates[[c for c in keep if c in candidates.columns]].copy()
            if weather_alerts.empty:
                weather_alerts = ranked_alerts
            else:
                weather_alerts["_source_rank"] = 0
                ranked_alerts["_source_rank"] = 1
                weather_alerts = pd.concat([weather_alerts, ranked_alerts], ignore_index=True, sort=False)
                weather_alerts = weather_alerts.sort_values(
                    ["_source_rank", "forecast_risk_score"],
                    ascending=[True, False],
                    na_position="last",
                )
                weather_alerts = weather_alerts.drop_duplicates(["sku", "location_id"], keep="first")
                weather_alerts = weather_alerts.drop(columns=["_source_rank"], errors="ignore")
    if weather_alerts.empty and not forecast_summary.empty:
        weather_alerts = forecast_summary[forecast_summary["uplift_vs_baseline_percent"] >= 20].copy()
        weather_alerts["priority"] = np.select(
            [weather_alerts["uplift_vs_baseline_percent"] >= 35, weather_alerts["uplift_vs_baseline_percent"] >= 20],
            ["critical", "high"],
            default="medium",
        )
        weather_alerts["alert_reason"] = "forecast peste baseline"
        weather_alerts["dealer_message"] = (
            weather_alerts["city"].astype(str)
            + ": spike estimat la "
            + weather_alerts["part_name"].astype(str)
            + ". Forecast 21 zile: "
            + weather_alerts["forecast_21d_units"].round(0).astype(int).astype(str)
            + " buc."
        )

    if weather_alerts.empty:
        return pd.DataFrame()

    merge_cols = [
        "sku",
        "location_id",
        "current_stock",
        "safety_stock",
        "optimal_stock",
        "lead_time_days",
        "supplier_id",
        "supplier_name",
        "recommended_action",
        "recommended_qty",
        "days_until_stockout",
        "coverage_ratio_horizon",
    ]
    rec_keep = [c for c in merge_cols if c in recommendations.columns]
    center = weather_alerts.merge(recommendations[rec_keep], on=["sku", "location_id"], how="left")
    center["alert_id"] = [
        f"ALRT-{row.location_id}-{row.sku}-{idx + 1:04d}" for idx, row in enumerate(center.itertuples())
    ]
    center["status"] = "new"
    center["owner_role"] = "dealer_parts_manager"
    inferred_alert_type = np.where(
        center.get("alert_reason", "").astype(str).str.contains("weather|frig|heatwave|zapada|ploaie", case=False, regex=True),
        "weather_demand_spike",
        "demand_spike",
    )
    if "alert_type" in center.columns:
        center["alert_type"] = center["alert_type"].fillna(pd.Series(inferred_alert_type, index=center.index))
    else:
        center["alert_type"] = inferred_alert_type
    center["next_best_action"] = np.where(
        center.get("recommended_action", "").fillna("") == "order",
        "place_supplier_order",
        "verify_stock_and_prepare_transfer",
    )
    center["action_detail"] = (
        "Comanda recomandata: "
        + center.get("recommended_qty", pd.Series([0] * len(center))).fillna(0).round(0).astype(int).astype(str)
        + " buc; lead time: "
        + center.get("lead_time_days", pd.Series([0] * len(center))).fillna(0).round(0).astype(int).astype(str)
        + " zile"
    )
    center["severity_score"] = (
        (4 - priority_rank(center["priority"])) * 20
        + center.get("uplift_vs_baseline_percent", pd.Series([0] * len(center))).clip(lower=0, upper=100) * 0.5
        + center.get("weather_sensitivity_score", pd.Series([0] * len(center))).fillna(0).clip(0, 3) * 10
    ).round(2)
    if "forecast_risk_score" not in center.columns:
        center["forecast_risk_score"] = np.nan
    center["alert_risk_score"] = center["forecast_risk_score"].fillna(center["severity_score"]).round(2)
    center["risk_rank"] = center["alert_risk_score"].rank(method="first", ascending=False).astype(int)
    center["decision_mode"] = "ranked_risk_signal"
    center["forecast_usage_note"] = "Forecastul este folosit ca ranking de risc, nu ca promisiune exacta de vanzari."
    center["rank_reason"] = (
        "risk_score="
        + center["alert_risk_score"].round(1).astype(str)
        + "; uplift="
        + center.get("uplift_vs_baseline_percent", pd.Series([0] * len(center))).fillna(0).round(0).astype(int).astype(str)
        + "%"
    )
    center = center.sort_values(["status", "alert_risk_score", "priority"], ascending=[True, False, True])
    ordered = [
        "alert_id",
        "status",
        "priority",
        "alert_type",
        "location_id",
        "city",
        "country_code",
        "sku",
        "part_name",
        "category",
        "forecast_21d_units",
        "baseline_21d_units",
        "uplift_vs_baseline_percent",
        "trigger_days",
        "current_stock",
        "days_until_stockout",
        "recommended_qty",
        "supplier_name",
        "alert_reason",
        "dealer_message",
        "next_best_action",
        "action_detail",
        "owner_role",
        "severity_score",
        "alert_risk_score",
        "risk_rank",
        "decision_mode",
        "rank_reason",
        "forecast_usage_note",
    ]
    return center[[c for c in ordered if c in center.columns]]


def build_stock_risk_engine(
    raw_dir: Path,
    processed_dir: Path,
    forecast_summary: pd.DataFrame,
    recommendations: pd.DataFrame,
    horizon: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    inventory = normalize_inventory(raw_dir, _read_csv(raw_dir / "inventory_snapshot.csv"))
    suppliers = _read_csv(raw_dir / "suppliers.csv").rename(columns={"country_code": "supplier_country_code"})
    if forecast_summary.empty or inventory.empty:
        return pd.DataFrame(), pd.DataFrame()
    default_supplier = str(suppliers["supplier_id"].iloc[0]) if "supplier_id" in suppliers.columns and not suppliers.empty else "UNKNOWN"

    cols = [
        "sku",
        "location_id",
        "current_stock",
        "safety_stock",
        "optimal_stock",
        "min_order_qty",
        "lead_time_days",
        "pending_order_qty",
        "supplier_id",
    ]
    stock = forecast_summary.merge(inventory[[c for c in cols if c in inventory.columns]], on=["sku", "location_id"], how="left")
    if "supplier_id" not in stock.columns:
        stock["supplier_id"] = stock["category"].map(lambda category: supplier_for_category(category, default_supplier))
    stock["supplier_id"] = stock["supplier_id"].fillna(stock["category"].map(lambda category: supplier_for_category(category, default_supplier)))
    if not suppliers.empty and "supplier_id" in stock.columns:
        stock = stock.merge(suppliers, on="supplier_id", how="left")
    for col in ["current_stock", "safety_stock", "optimal_stock", "min_order_qty", "lead_time_days", "pending_order_qty"]:
        if col not in stock.columns:
            stock[col] = 0
        stock[col] = pd.to_numeric(stock[col], errors="coerce").fillna(0)

    stock["available_stock"] = stock["current_stock"] + stock["pending_order_qty"]
    stock["lead_time_demand"] = stock["forecast_avg_daily"].fillna(0) * stock["lead_time_days"]
    stock["projected_stock_after_21d"] = stock["available_stock"] - stock["forecast_21d_units"].fillna(0)
    stock["coverage_days"] = safe_div(stock["available_stock"], stock["forecast_avg_daily"].replace(0, np.nan)).fillna(999).clip(upper=999)
    stock["required_stock"] = stock["lead_time_demand"] + stock["safety_stock"] + stock["forecast_peak_day_units"].fillna(0)
    stock["raw_reorder_need"] = stock["required_stock"] - stock["available_stock"]
    stock["recommended_order_qty"] = np.where(
        (stock["raw_reorder_need"] > 0) | (stock["projected_stock_after_21d"] < stock["safety_stock"]),
        np.maximum(stock["min_order_qty"], np.ceil(stock["raw_reorder_need"].clip(lower=0) + stock["forecast_avg_daily"].fillna(0) * 7)),
        0,
    ).astype(int)
    stock["risk_status"] = np.select(
        [
            stock["coverage_days"] <= stock["lead_time_days"],
            stock["projected_stock_after_21d"] < 0,
            stock["projected_stock_after_21d"] < stock["safety_stock"],
            stock["weather_spike_days"].fillna(0) > 0,
        ],
        ["critical", "high", "medium", "watch"],
        default="ok",
    )
    stock["lost_sales_risk_units"] = stock["projected_stock_after_21d"].clip(upper=0).abs().round(2)
    stock["reorder_message"] = np.where(
        stock["recommended_order_qty"] > 0,
        "Order "
        + stock["recommended_order_qty"].astype(str)
        + " buc pentru a acoperi lead time + safety stock.",
        "Monitorizeaza, stocul acopera scenariul curent.",
    )

    if not recommendations.empty:
        rec_cols = [c for c in ["sku", "location_id", "recommended_action", "recommended_qty", "priority", "explanation"] if c in recommendations.columns]
        stock = stock.merge(recommendations[rec_cols], on=["sku", "location_id"], how="left", suffixes=("", "_recommendation"))

    stock = stock.sort_values(
        ["risk_status", "recommended_order_qty", "uplift_vs_baseline_percent"],
        key=lambda s: priority_rank(s) if s.name == "risk_status" else s,
        ascending=[True, False, False],
    )

    transfer = _read_csv(processed_dir / "transfer_suggestions.csv")
    return stock, transfer


def build_product_sensitivity_profiles(
    processed_dir: Path,
    product_location_scores: pd.DataFrame,
) -> pd.DataFrame:
    if product_location_scores.empty:
        return pd.DataFrame()

    profiles = product_location_scores.copy()
    window_by_category = _read_csv(processed_dir / "sales_intelligence" / "window_diagnostics_by_category.csv")
    if not window_by_category.empty and {"category", "window_days", "WAPE_percent"}.issubset(window_by_category.columns):
        best_window = (
            window_by_category.sort_values("WAPE_percent")
            .drop_duplicates("category")[["category", "window_days", "WAPE_percent"]]
            .rename(columns={"window_days": "best_window_days", "WAPE_percent": "best_window_wape_percent"})
        )
        profiles = profiles.merge(best_window, on="category", how="left")
    else:
        profiles["best_window_days"] = 28
        profiles["best_window_wape_percent"] = np.nan

    uplift_cols = [c for c in profiles.columns if c.startswith("uplift_")]
    if uplift_cols:
        values = profiles[uplift_cols].fillna(0)
        profiles["primary_trigger"] = values.idxmax(axis=1).str.replace("uplift_", "", regex=False)
        profiles["primary_trigger_uplift_percent"] = values.max(axis=1).mul(100).round(1)
    else:
        profiles["primary_trigger"] = "seasonality"
        profiles["primary_trigger_uplift_percent"] = 0.0

    profiles["primary_trigger_label"] = profiles["primary_trigger"].map(TRIGGER_LABELS).fillna(profiles["primary_trigger"])
    profiles["sensitivity_segment"] = np.select(
        [
            profiles["weather_sensitivity_score"].fillna(0) >= 1.0,
            profiles["seasonality_score"].fillna(0) >= 1.5,
            profiles["volatility_score"].fillna(0) >= 1.0,
        ],
        ["weather_sensitive", "seasonal_outlier", "volatile_outlier"],
        default="stable_monitor",
    )
    profiles["profile_summary"] = (
        profiles["city"].astype(str)
        + " / "
        + profiles["part_name"].astype(str)
        + ": peak month "
        + profiles["peak_month"].fillna(0).astype(int).astype(str)
        + ", trigger "
        + profiles["primary_trigger_label"].astype(str)
        + " (+"
        + profiles["primary_trigger_uplift_percent"].fillna(0).astype(str)
        + "%), recommended window "
        + profiles["best_window_days"].fillna(28).astype(int).astype(str)
        + " zile."
    )
    keep = [
        "sku",
        "location_id",
        "part_name",
        "category",
        "city",
        "country_code",
        "climate_zone",
        "volatility_score",
        "seasonality_score",
        "weather_sensitivity_score",
        "business_impact_score",
        "peak_month",
        "primary_trigger",
        "primary_trigger_label",
        "primary_trigger_uplift_percent",
        "best_window_days",
        "best_window_wape_percent",
        "sensitivity_segment",
        "profile_summary",
    ]
    return profiles[[c for c in keep if c in profiles.columns]].sort_values(
        ["sensitivity_segment", "business_impact_score"], ascending=[True, False]
    )


def _trigger_effect(row: pd.Series) -> float:
    effect = 0.0
    mappings = [
        ("cold_snap_flag", "uplift_cold_snap_flag"),
        ("heatwave_flag", "uplift_heatwave_flag"),
        ("weather_spike_flag", "uplift_weather_spike_flag"),
        ("is_payday_window", "uplift_is_payday_window"),
    ]
    for flag, uplift in mappings:
        if row.get(flag, 0) == 1:
            effect += max(0.0, float(row.get(uplift, 0) or 0))
    if float(row.get("temp_change_3d_c", 0) or 0) <= -4:
        effect += max(0.0, float(row.get("uplift_temperature_drop_flag", 0) or 0))
    if float(row.get("temp_change_3d_c", 0) or 0) >= 4:
        effect += max(0.0, float(row.get("uplift_temperature_rise_flag", 0) or 0))
    return min(effect, 2.0)


def build_forecast_scenarios(
    processed_dir: Path,
    product_location_scores: pd.DataFrame,
    horizon: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    forecast = _read_csv(processed_dir / "forecast_30d.csv", parse_dates=["forecast_date"])
    if forecast.empty:
        return pd.DataFrame(), pd.DataFrame()
    pred_col = first_existing(forecast.columns, ["predicted_quantity", "forecast_quantity", "prediction", "yhat"])
    if pred_col is None:
        return pd.DataFrame(), pd.DataFrame()
    if "horizon_day" in forecast.columns:
        scenarios = forecast[forecast["horizon_day"] <= horizon].copy()
    else:
        scenarios = forecast.sort_values("forecast_date").groupby(["sku", "location_id"]).head(horizon).copy()

    uplift_cols = [c for c in product_location_scores.columns if c.startswith("uplift_")]
    keep = ["sku", "location_id", "seasonality_score", "weather_sensitivity_score"] + uplift_cols
    if not product_location_scores.empty:
        scenarios = scenarios.merge(product_location_scores[[c for c in keep if c in product_location_scores.columns]], on=["sku", "location_id"], how="left")
    for col in ["cold_snap_flag", "heatwave_flag", "weather_spike_flag", "is_payday_window", "temp_change_3d_c"]:
        if col not in scenarios.columns:
            scenarios[col] = 0
    for col in uplift_cols:
        if col not in scenarios.columns:
            scenarios[col] = 0.0
    scenarios["trigger_effect"] = scenarios.apply(_trigger_effect, axis=1)
    scenarios["expected_quantity"] = scenarios[pred_col].clip(lower=0)
    scenarios["mild_weather_quantity"] = safe_div(scenarios["expected_quantity"], 1 + scenarios["trigger_effect"] * 0.25).clip(lower=0)
    scenarios["severe_weather_quantity"] = scenarios["expected_quantity"] * (1 + scenarios["trigger_effect"] * 0.35)
    scenarios["promo_payday_quantity"] = scenarios["expected_quantity"] * (
        1 + np.where(scenarios["is_payday_window"] == 1, scenarios.get("uplift_is_payday_window", 0).fillna(0).clip(lower=0) * 0.35, 0)
    )
    scenarios["pessimistic_quantity"] = scenarios["mild_weather_quantity"] * 0.9
    scenarios["optimistic_quantity"] = np.maximum(scenarios["severe_weather_quantity"], scenarios["expected_quantity"] * 1.15)
    scenario_summary = (
        scenarios.groupby(["sku", "location_id"], as_index=False)
        .agg(
            part_name=("part_name", "first"),
            category=("category", "first"),
            city=("city", "first"),
            country_code=("country_code", "first"),
            expected_21d_units=("expected_quantity", "sum"),
            mild_weather_21d_units=("mild_weather_quantity", "sum"),
            severe_weather_21d_units=("severe_weather_quantity", "sum"),
            promo_payday_21d_units=("promo_payday_quantity", "sum"),
            pessimistic_21d_units=("pessimistic_quantity", "sum"),
            optimistic_21d_units=("optimistic_quantity", "sum"),
            max_trigger_effect=("trigger_effect", "max"),
            weather_spike_days=("weather_spike_flag", "sum"),
            payday_window_days=("is_payday_window", "sum"),
        )
    )
    for col in [c for c in scenario_summary.columns if c.endswith("_units")]:
        scenario_summary[col] = scenario_summary[col].round(2)
    scenario_summary["scenario_spread_units"] = (
        scenario_summary["optimistic_21d_units"] - scenario_summary["pessimistic_21d_units"]
    ).round(2)
    return scenarios, scenario_summary.sort_values("scenario_spread_units", ascending=False)


def build_risk_map(raw_dir: Path, dealer_alerts: pd.DataFrame, stock_risk: pd.DataFrame) -> pd.DataFrame:
    locations = normalize_locations(_read_csv(raw_dir / "eu_locations.csv"))
    if locations.empty:
        return pd.DataFrame()
    rows = locations[["location_id", "city", "country_code", "latitude", "longitude", "climate_zone"]].copy()
    if not dealer_alerts.empty:
        alert_counts = dealer_alerts.groupby("location_id").agg(
            total_alerts=("alert_id", "count"),
            critical_alerts=("priority", lambda s: int((s == "critical").sum())),
            high_alerts=("priority", lambda s: int((s == "high").sum())),
        )
        rows = rows.merge(alert_counts, on="location_id", how="left")
    if not stock_risk.empty:
        risk_counts = stock_risk.groupby("location_id").agg(
            critical_stock_risks=("risk_status", lambda s: int((s == "critical").sum())),
            high_stock_risks=("risk_status", lambda s: int((s == "high").sum())),
            recommended_order_units=("recommended_order_qty", "sum"),
        )
        rows = rows.merge(risk_counts, on="location_id", how="left")
    for col in ["total_alerts", "critical_alerts", "high_alerts", "critical_stock_risks", "high_stock_risks", "recommended_order_units"]:
        if col not in rows.columns:
            rows[col] = 0
        rows[col] = rows[col].fillna(0)
    rows["risk_score"] = (
        rows["critical_alerts"] * 5
        + rows["high_alerts"] * 3
        + rows["critical_stock_risks"] * 4
        + rows["high_stock_risks"] * 2
        + np.log1p(rows["recommended_order_units"])
    ).round(2)
    rows["risk_level"] = np.select(
        [rows["risk_score"] >= 25, rows["risk_score"] >= 12, rows["risk_score"] >= 4],
        ["critical", "high", "watch"],
        default="ok",
    )
    return rows.sort_values("risk_score", ascending=False)


def build_model_explainability(
    dealer_alerts: pd.DataFrame,
    sensitivity_profiles: pd.DataFrame,
    stock_risk: pd.DataFrame,
    processed_dir: Path,
) -> pd.DataFrame:
    if dealer_alerts.empty:
        return pd.DataFrame()
    profiles = sensitivity_profiles[["sku", "location_id", "primary_trigger_label", "sensitivity_segment", "profile_summary"]].copy() if not sensitivity_profiles.empty else pd.DataFrame()
    stock_cols = ["sku", "location_id", "risk_status", "coverage_days", "projected_stock_after_21d", "recommended_order_qty"]
    stock = stock_risk[[c for c in stock_cols if c in stock_risk.columns]].copy() if not stock_risk.empty else pd.DataFrame()
    explain = dealer_alerts.copy()
    if not profiles.empty:
        explain = explain.merge(profiles, on=["sku", "location_id"], how="left")
    if not stock.empty:
        explain = explain.merge(stock, on=["sku", "location_id"], how="left")

    metrics_path = processed_dir / "model_metrics.json"
    category_conf = {}
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for row in metrics.get("metrics_by_category", []):
            category_conf[row["category"]] = max(35.0, 100.0 - float(row.get("WAPE_percent", 65)))

    def drivers(row):
        parts = []
        if pd.notna(row.get("alert_reason")):
            parts.append(str(row["alert_reason"]))
        if pd.notna(row.get("primary_trigger_label")):
            parts.append(f"istoric sensibil la {row['primary_trigger_label']}")
        if float(row.get("uplift_vs_baseline_percent", 0) or 0) > 0:
            parts.append(f"forecast +{row['uplift_vs_baseline_percent']:.0f}% vs baseline")
        if pd.notna(row.get("risk_status")) and row.get("risk_status") != "ok":
            parts.append(f"risc stoc: {row['risk_status']}")
        return "; ".join(dict.fromkeys(parts))

    explain["driver_summary"] = explain.apply(drivers, axis=1)
    explain["confidence_proxy_percent"] = explain["category"].map(category_conf).fillna(55).round(1)
    explain["explainability_note"] = (
        "Predictia combina istoric SKU-location, sezonalitate, vreme, calendar si lag-uri. "
        "Confidence este proxy pe baza WAPE holdout pe categorie."
    )
    keep = [
        "alert_id",
        "priority",
        "location_id",
        "city",
        "sku",
        "part_name",
        "category",
        "driver_summary",
        "confidence_proxy_percent",
        "sensitivity_segment",
        "coverage_days",
        "projected_stock_after_21d",
        "recommended_order_qty",
        "dealer_message",
        "explainability_note",
    ]
    return explain[[c for c in keep if c in explain.columns]]


def build_model_monitoring(raw_dir: Path, processed_dir: Path, dealer_alerts: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    holdout = _read_csv(processed_dir / "holdout_predictions_sample.csv")
    if holdout.empty:
        summary = {"generated_at_utc": _now_utc(), "status": "missing_holdout_predictions"}
        return summary, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    holdout["error"] = holdout["prediction"] - holdout["quantity_sold"]
    holdout["abs_error"] = holdout["error"].abs()
    holdout["ape"] = np.where(holdout["quantity_sold"] > 0, holdout["abs_error"] / holdout["quantity_sold"] * 100, np.nan)

    by_category = (
        holdout.groupby("category", as_index=False)
        .agg(
            MAE=("abs_error", "mean"),
            WAPE_percent=("abs_error", lambda s: safe_div(s.sum(), holdout.loc[s.index, "quantity_sold"].abs().sum()) * 100),
            bias_units=("error", "mean"),
            n_rows=("error", "size"),
        )
        .round(4)
    )
    by_pair = (
        holdout.groupby(["sku", "location_id"], as_index=False)
        .agg(
            category=("category", "first"),
            MAE=("abs_error", "mean"),
            WAPE_percent=("abs_error", lambda s: safe_div(s.sum(), holdout.loc[s.index, "quantity_sold"].abs().sum()) * 100),
            bias_units=("error", "mean"),
            n_rows=("error", "size"),
        )
        .round(4)
        .sort_values("WAPE_percent", ascending=False)
    )

    sales = _read_csv(raw_dir / "sales_history.csv", parse_dates=["date"])
    drift = pd.DataFrame()
    if not sales.empty:
        if "stockout_flag" not in sales.columns:
            if "stock_end" in sales.columns:
                sales["stockout_flag"] = (pd.to_numeric(sales["stock_end"], errors="coerce").fillna(1) <= 0).astype(int)
            else:
                sales["stockout_flag"] = 0
        max_date = sales["date"].max()
        current = sales[sales["date"] > max_date - pd.Timedelta(days=90)].copy()
        previous = sales[(sales["date"] <= max_date - pd.Timedelta(days=90)) & (sales["date"] > max_date - pd.Timedelta(days=180))].copy()
        current["period"] = "current_90d"
        previous["period"] = "previous_90d"
        drift_base = pd.concat([current, previous], ignore_index=True)
        drift = (
            drift_base.groupby(["category", "period"], as_index=False)
            .agg(
                avg_daily_sales=("quantity_sold", "mean"),
                avg_temp_c=("temperature_c", "mean"),
                weather_spike_rate=("weather_spike_flag", "mean"),
                stockout_rate=("stockout_flag", "mean"),
            )
            .pivot(index="category", columns="period")
        )
        drift.columns = [f"{metric}_{period}" for metric, period in drift.columns]
        drift = drift.reset_index()
        for metric in ["avg_daily_sales", "avg_temp_c", "weather_spike_rate", "stockout_rate"]:
            cur = f"{metric}_current_90d"
            prev = f"{metric}_previous_90d"
            if cur in drift.columns and prev in drift.columns:
                drift[f"{metric}_delta"] = (drift[cur] - drift[prev]).round(4)

    summary = {
        "generated_at_utc": _now_utc(),
        "holdout_rows": int(len(holdout)),
        "overall_MAE": round(float(holdout["abs_error"].mean()), 4),
        "overall_WAPE_percent": round(float(safe_div(holdout["abs_error"].sum(), holdout["quantity_sold"].abs().sum()) * 100), 4),
        "overall_bias_units": round(float(holdout["error"].mean()), 4),
        "active_dealer_alerts": int(len(dealer_alerts)),
        "critical_dealer_alerts": int((dealer_alerts.get("priority", pd.Series(dtype=str)) == "critical").sum()) if not dealer_alerts.empty else 0,
        "monitoring_recommendation": "Retrain if WAPE grows by 10pp, bias exceeds +/-0.5 units, or data drift persists for 2 refresh cycles.",
    }
    segmented_21d = _read_csv(processed_dir / "segmented_21d_metrics.csv")
    if not segmented_21d.empty:
        overall = segmented_21d[segmented_21d["segment"] == "overall_21d"]
        if not overall.empty:
            summary["overall_21d_WAPE_percent"] = float(overall["WAPE_percent"].iloc[0])
            summary["overall_21d_MAE"] = float(overall["MAE"].iloc[0])
    backtest_path = processed_dir / "business_alert_backtest_21d.json"
    if backtest_path.exists():
        summary["business_alert_backtest_21d"] = json.loads(backtest_path.read_text(encoding="utf-8"))
    return summary, by_category, by_pair, drift


def build_data_integrations(raw_dir: Path, processed_dir: Path) -> tuple[pd.DataFrame, dict]:
    definitions = [
        ("POS sales", "available", raw_dir / "sales_history.csv", "Core demand history and sell-rate."),
        ("Inventory snapshot", "available", raw_dir / "inventory_snapshot.csv", "Current stock, safety stock, MOQ, lead time."),
        ("Supplier master", "available", raw_dir / "suppliers.csv", "Supplier reliability and delay risk."),
        ("Weather API", "simulated", raw_dir / "weather_daily.csv", "Forecast weather drivers; replace with live API in production."),
        ("Calendar events", "available", raw_dir / "calendar_daily.csv", "Holidays, payday windows, campaigns."),
        ("Service appointments", "not_connected", raw_dir / "service_appointments.csv", "Forward-looking workshop demand signal."),
        ("Vehicle parc / VIO", "not_connected", raw_dir / "vehicle_parc.csv", "Regional vehicle population and engine mix."),
        ("Promotions", "available", raw_dir / "calendar_events.csv", "Campaign and promotion uplift."),
        ("Fuel and mobility index", "available", raw_dir / "sales_history.csv", "Mobility context already embedded in generated sales data."),
        ("Forecast model outputs", "available", processed_dir / "forecast_30d.csv", "Demand forecast consumed by alerts and reorder logic."),
    ]
    rows = []
    for name, status, path, purpose in definitions:
        exists = path.exists()
        row_count = 0
        max_date = ""
        if exists and path.suffix.lower() == ".csv":
            try:
                sample = pd.read_csv(path)
                row_count = int(len(sample))
                if "date" in sample.columns:
                    max_date = str(sample["date"].max())
                elif "forecast_date" in sample.columns:
                    max_date = str(sample["forecast_date"].max())
            except Exception:
                row_count = 0
        rows.append(
            {
                "integration_name": name,
                "status": status if exists or status == "not_connected" else "missing",
                "path": str(path),
                "exists": bool(exists),
                "row_count": row_count,
                "latest_date": max_date,
                "purpose": purpose,
                "production_next_step": "Map real client source and validate schema." if status != "available" else "Keep freshness checks active.",
            }
        )
    catalog = pd.DataFrame(rows)
    health = {
        "generated_at_utc": _now_utc(),
        "available_count": int((catalog["status"] == "available").sum()),
        "simulated_count": int((catalog["status"] == "simulated").sum()),
        "not_connected_count": int((catalog["status"] == "not_connected").sum()),
        "missing_count": int((catalog["status"] == "missing").sum()),
        "integrations": _records(catalog),
    }
    return catalog, health


def save_charts(out_dir: Path, dealer_alerts: pd.DataFrame, stock_risk: pd.DataFrame, scenario_summary: pd.DataFrame, risk_map: pd.DataFrame, monitoring_by_category: pd.DataFrame) -> None:
    chart_dir = out_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    if not risk_map.empty:
        fig = px.scatter_geo(
            risk_map,
            lat="latitude",
            lon="longitude",
            color="risk_level",
            size=risk_map["total_alerts"].clip(lower=1),
            hover_name="city",
            hover_data=["location_id", "risk_score", "total_alerts", "critical_stock_risks", "recommended_order_units"],
            title="Dealer risk map",
            scope="europe",
        )
        fig.update_geos(fitbounds="locations", visible=True)
        fig.write_html(chart_dir / "dealer_risk_map.html")

    if not stock_risk.empty:
        top = stock_risk.sort_values("recommended_order_qty", ascending=False).head(25)
        fig = px.bar(
            top,
            x="recommended_order_qty",
            y="part_name",
            color="risk_status",
            orientation="h",
            hover_data=["city", "sku", "current_stock", "coverage_days", "reorder_message"],
            title="Top reorder recommendations",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        fig.write_html(chart_dir / "stock_risk_reorder.html")

    if not scenario_summary.empty:
        top = scenario_summary.head(20)
        fig = px.bar(
            top,
            x="part_name",
            y=["pessimistic_21d_units", "expected_21d_units", "optimistic_21d_units"],
            color_discrete_sequence=["#6baed6", "#2171b5", "#fb6a4a"],
            hover_data=["city", "sku", "scenario_spread_units", "weather_spike_days"],
            title="Forecast scenarios: pessimistic vs expected vs optimistic",
        )
        fig.update_layout(xaxis_tickangle=-35)
        fig.write_html(chart_dir / "forecast_scenarios.html")

    if not dealer_alerts.empty:
        fig = px.bar(
            dealer_alerts.head(30),
            x="severity_score",
            y="part_name",
            color="priority",
            orientation="h",
            hover_data=["city", "sku", "dealer_message", "next_best_action"],
            title="Dealer alert center",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        fig.write_html(chart_dir / "dealer_alert_center.html")

    if not monitoring_by_category.empty:
        fig = px.bar(
            monitoring_by_category.sort_values("WAPE_percent", ascending=False),
            x="category",
            y="WAPE_percent",
            color="bias_units",
            title="Model monitoring by category",
        )
        fig.update_layout(xaxis_tickangle=-35)
        fig.write_html(chart_dir / "model_monitoring.html")


def generate_decision_layer(
    raw_dir: str | Path = "data/raw",
    processed_dir: str | Path = "data/processed",
    horizon: int = DEFAULT_HORIZON,
) -> Dict[str, object]:
    raw_path = Path(raw_dir)
    processed_path = Path(processed_dir)
    out_dir = processed_path / "decision_layer"
    out_dir.mkdir(parents=True, exist_ok=True)

    recommendations = _read_csv(processed_path / "recommendations.csv")
    product_location_scores = ensure_product_location_scores(raw_path, processed_path)
    forecast_summary = ensure_forecast_summary(raw_path, processed_path, horizon)

    dealer_alerts = build_dealer_alert_center(processed_path, forecast_summary, recommendations)
    stock_risk, transfer_suggestions = build_stock_risk_engine(raw_path, processed_path, forecast_summary, recommendations, horizon)
    sensitivity_profiles = build_product_sensitivity_profiles(processed_path, product_location_scores)
    scenario_daily, scenario_summary = build_forecast_scenarios(processed_path, product_location_scores, horizon)
    risk_map = build_risk_map(raw_path, dealer_alerts, stock_risk)
    explainability = build_model_explainability(dealer_alerts, sensitivity_profiles, stock_risk, processed_path)
    monitoring_summary, monitoring_by_category, monitoring_by_pair, drift_report = build_model_monitoring(raw_path, processed_path, dealer_alerts)
    integrations, integration_health = build_data_integrations(raw_path, processed_path)
    segmented_21d = _read_csv(processed_path / "segmented_21d_metrics.csv")
    segmented_daily = _read_csv(processed_path / "segmented_daily_metrics.csv")
    business_backtest = _read_csv(processed_path / "business_alert_backtest_21d.csv")

    outputs = {
        "dealer_alert_center.csv": dealer_alerts,
        "stock_risk_reorder_engine.csv": stock_risk,
        "transfer_suggestions_decision.csv": transfer_suggestions,
        "product_sensitivity_profiles.csv": sensitivity_profiles,
        "forecast_scenarios_daily.csv": scenario_daily,
        "forecast_scenarios_21d.csv": scenario_summary,
        "dealer_risk_map.csv": risk_map,
        "model_explainability.csv": explainability,
        "model_monitoring_by_category.csv": monitoring_by_category,
        "model_monitoring_by_sku_location.csv": monitoring_by_pair,
        "data_drift_report.csv": drift_report,
        "segmented_21d_metrics.csv": segmented_21d,
        "segmented_daily_metrics.csv": segmented_daily,
        "business_alert_backtest_21d.csv": business_backtest,
        "data_integrations_catalog.csv": integrations,
    }
    for filename, df in outputs.items():
        if isinstance(df, pd.DataFrame):
            df.to_csv(out_dir / filename, index=False)

    _write_json(out_dir / "dealer_alert_center.json", _records(dealer_alerts))
    _write_json(out_dir / "product_sensitivity_profiles.json", _records(sensitivity_profiles))
    _write_json(out_dir / "forecast_scenarios_21d.json", _records(scenario_summary))
    _write_json(out_dir / "dealer_risk_map.json", _records(risk_map))
    _write_json(out_dir / "model_explainability.json", _records(explainability))
    _write_json(out_dir / "model_monitoring_summary.json", monitoring_summary)
    _write_json(out_dir / "data_integrations_health.json", integration_health)

    save_charts(out_dir, dealer_alerts, stock_risk, scenario_summary, risk_map, monitoring_by_category)

    manifest = {
        "generated_at_utc": _now_utc(),
        "horizon_days": horizon,
        "features_added": [
            "dealer_alert_center",
            "stock_risk_reorder_engine",
            "product_sensitivity_profiles",
            "forecast_scenarios",
            "dealer_risk_map",
            "model_explainability",
            "model_monitoring",
            "data_integrations_catalog",
        ],
        "row_counts": {
            "dealer_alerts": int(len(dealer_alerts)),
            "stock_risk_rows": int(len(stock_risk)),
            "sensitivity_profiles": int(len(sensitivity_profiles)),
            "scenario_rows": int(len(scenario_summary)),
            "risk_map_locations": int(len(risk_map)),
            "explainability_rows": int(len(explainability)),
            "integrations": int(len(integrations)),
        },
        "output_dir": str(out_dir),
    }
    _write_json(out_dir / "decision_layer_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(generate_decision_layer(), indent=2))
