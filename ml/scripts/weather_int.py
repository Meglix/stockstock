from pathlib import Path
import json
import textwrap

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = PROCESSED_DIR / "sales_intelligence"
STATIC_CHART_DIR = OUT_DIR / "static_charts"
CHART_DIR = OUT_DIR / "interactive_charts"
LEGACY_PLOT_DIR = PROCESSED_DIR / "sales_plots"
OUTLIER_FORECAST_DIR = STATIC_CHART_DIR / "outlier_forecasts"

OUT_DIR.mkdir(parents=True, exist_ok=True)
STATIC_CHART_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_PLOT_DIR.mkdir(parents=True, exist_ok=True)
OUTLIER_FORECAST_DIR.mkdir(parents=True, exist_ok=True)

HORIZON_DAYS = 21
WINDOW_CANDIDATES = [7, 14, 21, 28, 42, 56]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

WEATHER_TRIGGERS = [
    "cold_snap_flag",
    "heatwave_flag",
    "weather_spike_flag",
    "temperature_drop_flag",
    "temperature_rise_flag",
]
BUSINESS_TRIGGERS = WEATHER_TRIGGERS + [
    "is_payday_window",
    "promotion_flag",
    "service_campaign_flag",
]
TRIGGER_LABELS = {
    "cold_snap_flag": "cold snap",
    "heatwave_flag": "heatwave",
    "weather_spike_flag": "weather spike",
    "temperature_drop_flag": "temp drop",
    "temperature_rise_flag": "temp rise",
    "is_payday_window": "payday",
    "promotion_flag": "promo",
    "service_campaign_flag": "service campaign",
}


def first_existing(columns, candidates):
    for col in candidates:
        if col in columns:
            return col
    return None


def short_label(value, width=42):
    return textwrap.shorten(str(value), width=width, placeholder="...")


def safe_ratio(num, den):
    if isinstance(num, (pd.Series, np.ndarray)) or isinstance(den, (pd.Series, np.ndarray)):
        return num / (den + 1e-6)
    return float(num) / float(den + 1e-6)


def save_static(fig, name):
    path = STATIC_CHART_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved: {path}")


def configure_matplotlib():
    plt.rcParams.update(
        {
            "figure.facecolor": "#f6f8fb",
            "axes.facecolor": "white",
            "axes.edgecolor": "#d7dde8",
            "axes.grid": True,
            "grid.color": "#e7ebf2",
            "grid.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
            "axes.titleweight": "bold",
            "axes.titlepad": 12,
        }
    )


def add_lookup_columns(df, lookup, key, columns):
    available = [c for c in columns if c in lookup.columns and c not in df.columns]
    if not available:
        return df
    return df.merge(lookup[[key] + available].drop_duplicates(key), on=key, how="left")


def load_sales_data():
    df = pd.read_csv(RAW_DIR / "sales_history.csv", parse_dates=["date"])

    parts_path = RAW_DIR / "parts_master.csv"
    if parts_path.exists():
        parts = pd.read_csv(parts_path)
        df = add_lookup_columns(
            df,
            parts,
            "sku",
            ["part_name", "category", "seasonality_profile", "unit_price_eur"],
        )

    loc_path = RAW_DIR / "eu_locations.csv"
    if loc_path.exists():
        locs = pd.read_csv(loc_path)
        df = add_lookup_columns(
            df,
            locs,
            "location_id",
            ["city", "country", "country_code", "climate_zone"],
        )

    fallback_cols = {
        "part_name": "sku",
        "category": "unknown",
        "seasonality_profile": "unknown",
        "city": "location_id",
        "country": "",
        "country_code": "",
        "climate_zone": "unknown",
    }
    for col, fallback in fallback_cols.items():
        if col not in df.columns:
            df[col] = df[fallback] if fallback in df.columns else fallback
    return df


def uplift_ratio(group, trigger, target_col="quantity_sold"):
    on = group[group[trigger] == 1][target_col]
    off = group[group[trigger] == 0][target_col]
    if len(on) < 5 or len(off) < 5:
        return 0.0
    return safe_ratio(on.mean() - off.mean(), off.mean())


def capped_days(value, horizon=HORIZON_DAYS):
    if pd.isna(value):
        return 0
    return int(np.clip(float(value), 0, horizon))


def max_days(row, columns, horizon=HORIZON_DAYS):
    values = [float(row.get(col, 0) or 0) for col in columns]
    return capped_days(max(values, default=0), horizon)


def add_forecast_risk_day_columns(fc):
    risk = fc.copy()
    risk_defs = {
        "_cold_risk_flag": ["cold_snap_flag", "temperature_drop_flag", "snow_flag"],
        "_heat_risk_flag": ["heatwave_flag", "temperature_rise_flag"],
        "_wet_risk_flag": ["rain_flag", "snow_flag"],
        "_weather_risk_flag": ["cold_snap_flag", "heatwave_flag", "weather_spike_flag", "temperature_drop_flag", "temperature_rise_flag", "rain_flag", "snow_flag"],
        "_business_trigger_flag": [
            "cold_snap_flag",
            "heatwave_flag",
            "weather_spike_flag",
            "temperature_drop_flag",
            "temperature_rise_flag",
            "rain_flag",
            "snow_flag",
            "is_payday_window",
        ],
    }
    for out_col, cols in risk_defs.items():
        available = [c for c in cols if c in risk.columns]
        if available:
            risk[out_col] = risk[available].fillna(0).astype(float).max(axis=1).clip(0, 1).astype(int)
        else:
            risk[out_col] = 0
    return risk


def build_weather_trigger_effects(df, min_trigger_days=20, min_normal_days=60):
    if df.empty:
        return pd.DataFrame()
    data = df.copy()
    if "month" not in data.columns:
        data["month"] = data["date"].dt.month
    triggers = [c for c in WEATHER_TRIGGERS if c in data.columns]
    rows = []
    for (sku, part_name, category), group in data.groupby(["sku", "part_name", "category"], sort=False):
        for trigger in triggers:
            on = group[group[trigger] == 1]
            if len(on) < min_trigger_days:
                continue
            # Compare trigger days with non-trigger days from the same months to avoid
            # mistaking normal seasonality for weather sensitivity.
            trigger_months = on["month"].dropna().unique()
            off = group[(group[trigger] == 0) & (group["month"].isin(trigger_months))]
            if len(off) < min_normal_days:
                continue
            normal_mean = float(off["quantity_sold"].mean())
            trigger_mean = float(on["quantity_sold"].mean())
            if normal_mean <= 0:
                continue
            uplift = safe_ratio(trigger_mean - normal_mean, normal_mean) * 100
            rows.append(
                {
                    "sku": sku,
                    "part_name": part_name,
                    "category": category,
                    "trigger": trigger,
                    "trigger_label": TRIGGER_LABELS.get(trigger, trigger),
                    "trigger_days": int(len(on)),
                    "normal_days_same_season": int(len(off)),
                    "avg_sales_trigger": round(trigger_mean, 2),
                    "avg_sales_normal_same_season": round(normal_mean, 2),
                    "uplift_percent": round(float(uplift), 1),
                    "reliability_score": round(float(max(uplift, 0) * np.log1p(len(on))), 3),
                }
            )
    effects = pd.DataFrame(rows)
    if effects.empty:
        return effects
    return effects.sort_values(["reliability_score", "uplift_percent"], ascending=False)


def product_explanation(row):
    pieces = []
    peak = int(row["peak_month"])
    if row["seasonality_score"] >= 0.35:
        pieces.append(f"seasonal peak in {MONTH_LABELS[peak - 1]}")
    if row["weather_sensitivity_score"] >= 0.15:
        pieces.append("weather-sensitive demand")
    if row["volatility_score"] >= 0.35:
        pieces.append("volatile daily sales")

    uplift_cols = [c for c in row.index if c.startswith("uplift_")]
    ranked = sorted(
        [(c.replace("uplift_", ""), row[c]) for c in uplift_cols],
        key=lambda item: item[1],
        reverse=True,
    )
    for trigger, value in ranked[:2]:
        if value >= 0.10:
            pieces.append(f"{TRIGGER_LABELS.get(trigger, trigger)} +{value * 100:.0f}%")

    if not pieces:
        pieces.append("stable demand profile")
    return "; ".join(pieces)


def compute_business_impact_scores(df):
    data = df.copy()
    data["month"] = data["date"].dt.month
    triggers = [c for c in BUSINESS_TRIGGERS if c in data.columns]

    rows = []
    for sku, group in data.groupby("sku", sort=False):
        daily = group.groupby("date")["quantity_sold"].sum()
        monthly = group.groupby("month")["quantity_sold"].mean().reindex(range(1, 13), fill_value=0)

        avg_daily = float(daily.mean())
        volatility = safe_ratio(daily.std(ddof=0), avg_daily)
        seasonality = safe_ratio(monthly.max() - monthly.min(), monthly.mean())
        revenue_proxy = (
            float(group["revenue_eur"].sum())
            if "revenue_eur" in group.columns
            else float(group["quantity_sold"].sum() * group.get("unit_price_eur", pd.Series([50])).mean())
        )
        uplift_values = {trigger: uplift_ratio(group, trigger) for trigger in triggers}
        weather_sensitivity = max([max(0.0, uplift_values.get(t, 0.0)) for t in WEATHER_TRIGGERS], default=0.0)

        rows.append(
            {
                "sku": sku,
                "part_name": group["part_name"].iloc[0],
                "category": group["category"].iloc[0],
                "avg_daily_sales": round(avg_daily, 4),
                "revenue_proxy_eur": round(revenue_proxy, 2),
                "volatility_score": round(volatility, 4),
                "seasonality_score": round(seasonality, 4),
                "weather_sensitivity_score": round(weather_sensitivity, 4),
                "peak_month": int(monthly.idxmax()),
                **{f"uplift_{k}": round(v, 4) for k, v in uplift_values.items()},
            }
        )

    scores = pd.DataFrame(rows)
    if scores.empty:
        return scores

    rank_cols = {
        "revenue_proxy_eur": 0.30,
        "seasonality_score": 0.25,
        "weather_sensitivity_score": 0.25,
        "volatility_score": 0.15,
        "avg_daily_sales": 0.05,
    }
    score = np.zeros(len(scores))
    for col, weight in rank_cols.items():
        score += scores[col].rank(pct=True).fillna(0) * weight
    scores["business_impact_score"] = (score * 100).round(2)
    scores["business_explanation"] = scores.apply(product_explanation, axis=1)
    scores = scores.sort_values("business_impact_score", ascending=False)

    scores.to_csv(OUT_DIR / "business_impact_scores.csv", index=False)
    scores.to_csv(OUT_DIR / "product_explainability.csv", index=False)
    (OUT_DIR / "product_explainability.json").write_text(
        json.dumps(scores.to_dict("records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return scores


def compute_product_location_scores(df):
    data = df.copy()
    data["month"] = data["date"].dt.month
    triggers = [c for c in BUSINESS_TRIGGERS if c in data.columns]
    rows = []

    for (sku, location_id), group in data.groupby(["sku", "location_id"], sort=False):
        daily = group.groupby("date")["quantity_sold"].sum()
        monthly = group.groupby("month")["quantity_sold"].mean().reindex(range(1, 13), fill_value=0)
        avg_daily = float(daily.mean())
        uplift_values = {trigger: uplift_ratio(group, trigger) for trigger in triggers}
        weather_sensitivity = max([max(0.0, uplift_values.get(t, 0.0)) for t in WEATHER_TRIGGERS], default=0.0)
        revenue_proxy = (
            float(group["revenue_eur"].sum())
            if "revenue_eur" in group.columns
            else float(group["quantity_sold"].sum() * group.get("unit_price_eur", pd.Series([50])).mean())
        )
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
                "revenue_proxy_eur": round(revenue_proxy, 2),
                "volatility_score": round(safe_ratio(daily.std(ddof=0), avg_daily), 4),
                "seasonality_score": round(safe_ratio(monthly.max() - monthly.min(), monthly.mean()), 4),
                "weather_sensitivity_score": round(weather_sensitivity, 4),
                "peak_month": int(monthly.idxmax()),
                **{f"uplift_{k}": round(v, 4) for k, v in uplift_values.items()},
            }
        )

    scores = pd.DataFrame(rows)
    if not scores.empty:
        score = (
            scores["revenue_proxy_eur"].rank(pct=True) * 0.25
            + scores["seasonality_score"].rank(pct=True) * 0.25
            + scores["weather_sensitivity_score"].rank(pct=True) * 0.25
            + scores["volatility_score"].rank(pct=True) * 0.15
            + scores["avg_daily_sales"].rank(pct=True) * 0.10
        )
        scores["business_impact_score"] = (score * 100).round(2)
        scores = scores.sort_values("business_impact_score", ascending=False)
    scores.to_csv(OUT_DIR / "product_location_scores.csv", index=False)
    return scores


def compute_window_diagnostics(df, windows=WINDOW_CANDIDATES):
    base = df[["date", "sku", "location_id", "category", "quantity_sold"]].copy()
    base = base.sort_values(["sku", "location_id", "date"])
    max_date = base["date"].max()
    eval_from = max_date - pd.Timedelta(days=365)
    eval_base = base[base["date"] >= eval_from].copy()

    summary_rows = []
    category_rows = []
    for window in windows:
        min_periods = max(3, window // 3)
        pred = (
            base.groupby(["sku", "location_id"], sort=False)["quantity_sold"]
            .transform(lambda s: s.shift(1).rolling(window, min_periods=min_periods).mean())
        )
        scored = base.assign(prediction=pred)
        scored = scored[scored["date"] >= eval_from].dropna(subset=["prediction"]).copy()
        scored["abs_error"] = (scored["quantity_sold"] - scored["prediction"]).abs()

        summary_rows.append(
            {
                "window_days": window,
                "MAE": round(float(scored["abs_error"].mean()), 4),
                "WAPE_percent": round(safe_ratio(scored["abs_error"].sum(), scored["quantity_sold"].abs().sum()) * 100, 4),
                "rows_evaluated": int(len(scored)),
                "eval_start_date": eval_from.date().isoformat(),
                "eval_end_date": max_date.date().isoformat(),
            }
        )
        for category, group in scored.groupby("category"):
            category_rows.append(
                {
                    "category": category,
                    "window_days": window,
                    "MAE": round(float(group["abs_error"].mean()), 4),
                    "WAPE_percent": round(safe_ratio(group["abs_error"].sum(), group["quantity_sold"].abs().sum()) * 100, 4),
                    "rows_evaluated": int(len(group)),
                }
            )

    summary = pd.DataFrame(summary_rows).sort_values("window_days")
    by_category = pd.DataFrame(category_rows).sort_values(["category", "window_days"])
    summary.to_csv(OUT_DIR / "window_diagnostics_summary.csv", index=False)
    by_category.to_csv(OUT_DIR / "window_diagnostics_by_category.csv", index=False)

    best = summary.loc[summary["WAPE_percent"].idxmin()]
    (OUT_DIR / "recommended_window.json").write_text(
        json.dumps(
            {
                "recommended_window_days": int(best["window_days"]),
                "selection_metric": "lowest WAPE on last 365 historical days",
                "WAPE_percent": float(best["WAPE_percent"]),
                "MAE": float(best["MAE"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary, by_category


def add_forecast_flags(forecast):
    fc = forecast.copy()
    if "temp_change_3d_c" in fc.columns:
        fc["temperature_drop_flag"] = (pd.to_numeric(fc["temp_change_3d_c"], errors="coerce").fillna(0) <= -4).astype(int)
        fc["temperature_rise_flag"] = (pd.to_numeric(fc["temp_change_3d_c"], errors="coerce").fillna(0) >= 4).astype(int)
    else:
        fc["temperature_drop_flag"] = 0
        fc["temperature_rise_flag"] = 0
    fc["rain_flag"] = (pd.to_numeric(fc.get("rain_mm", 0), errors="coerce").fillna(0) >= 4).astype(int)
    fc["snow_flag"] = (pd.to_numeric(fc.get("snow_cm", 0), errors="coerce").fillna(0) > 0).astype(int)
    for col in ["cold_snap_flag", "heatwave_flag", "weather_spike_flag", "is_payday_window"]:
        if col not in fc.columns:
            fc[col] = 0
    return fc


def product_trigger_rules(row):
    sku = str(row.get("sku", "")).upper()
    category = str(row.get("category", "")).lower()
    reasons = []

    cold_days = capped_days(row.get("cold_risk_days", max_days(row, ["cold_snap_days", "temperature_drop_days", "snow_days"])))
    heat_days = capped_days(row.get("heat_risk_days", max_days(row, ["heatwave_days", "temperature_rise_days"])))
    wet_days = capped_days(row.get("wet_risk_days", max_days(row, ["rain_days", "snow_days"])))
    payday_days = capped_days(row.get("payday_window_days", 0))
    spike_days = capped_days(row.get("weather_spike_days", 0))

    if category in ["battery", "winter_fluids", "coolant"] and cold_days > 0:
        reasons.append(f"{cold_days}/{HORIZON_DAYS} zile frig/zapada")
    if category in ["wipers"] and wet_days > 0:
        reasons.append(f"{wet_days}/{HORIZON_DAYS} zile ploaie/zapada")
    if category in ["ac_cooling", "filters", "coolant"] and heat_days > 0:
        reasons.append(f"{heat_days}/{HORIZON_DAYS} zile incalzire/heatwave")
    if category in ["maintenance", "brakes", "tires", "battery"] and payday_days > 0:
        reasons.append(f"{payday_days}/{HORIZON_DAYS} zile in fereastra payday")
    if spike_days > 0 and category in ["winter_fluids", "battery", "wipers", "ac_cooling", "coolant"]:
        reasons.append(f"{spike_days}/{HORIZON_DAYS} zile cu weather spike")

    if ("WIPER" in sku or "STERG" in sku) and wet_days > 0 and not any("ploaie" in r for r in reasons):
        reasons.append(f"{wet_days}/{HORIZON_DAYS} zile ploaie/zapada")
    if ("AC" in sku or "CABIN" in sku) and heat_days > 0 and not any("heatwave" in r for r in reasons):
        reasons.append(f"{heat_days}/{HORIZON_DAYS} zile incalzire/heatwave")
    return reasons


def historical_baseline(df, horizon=HORIZON_DAYS):
    hist = df.sort_values(["sku", "location_id", "date"]).copy()
    trailing = hist.groupby(["sku", "location_id"], sort=False).tail(56)
    baseline = (
        trailing.groupby(["sku", "location_id"], as_index=False)
        .agg(
            baseline_avg_daily=("quantity_sold", "mean"),
            baseline_last_21d_units=("quantity_sold", lambda s: float(s.tail(horizon).sum())),
        )
    )
    baseline["baseline_21d_units"] = baseline["baseline_avg_daily"] * horizon
    return baseline


def generate_weather_sales_alerts(df, location_scores=None, horizon=HORIZON_DAYS):
    forecast_path = PROCESSED_DIR / "forecast_30d.csv"
    empty_cols = [
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
    ]
    if not forecast_path.exists():
        alerts = pd.DataFrame(columns=empty_cols)
        alerts.to_csv(OUT_DIR / "weather_sales_alerts_21d.csv", index=False)
        return alerts, pd.DataFrame()

    forecast = pd.read_csv(forecast_path)
    date_col = first_existing(forecast.columns, ["forecast_date", "date"])
    pred_col = first_existing(
        forecast.columns,
        ["predicted_quantity", "forecast_quantity", "prediction", "yhat", "quantity_forecast"],
    )
    if pred_col is None:
        raise ValueError("Nu am gasit coloana de predictie in forecast_30d.csv")

    if date_col:
        forecast[date_col] = pd.to_datetime(forecast[date_col])
    if "horizon_day" in forecast.columns:
        fc21 = forecast[forecast["horizon_day"] <= horizon].copy()
    elif date_col:
        fc21 = forecast.sort_values(date_col).groupby(["sku", "location_id"]).head(horizon).copy()
    else:
        fc21 = forecast.groupby(["sku", "location_id"]).head(horizon).copy()

    fc21 = add_forecast_flags(fc21)
    fc21 = add_forecast_risk_day_columns(fc21)
    for col in ["part_name", "category", "city", "country_code", "climate_zone", "temperature_c", "rain_mm", "snow_cm"]:
        if col not in fc21.columns:
            fc21[col] = "" if col in ["part_name", "category", "city", "country_code", "climate_zone"] else 0

    forecast_summary = (
        fc21.groupby(["sku", "location_id"], as_index=False)
        .agg(
            part_name=("part_name", "first"),
            category=("category", "first"),
            city=("city", "first"),
            country_code=("country_code", "first"),
            climate_zone=("climate_zone", "first"),
            forecast_21d_units=(pred_col, "sum"),
            forecast_avg_daily=(pred_col, "mean"),
            forecast_peak_day_units=(pred_col, "max"),
            avg_temp_c=("temperature_c", "mean"),
            min_temp_c=("temperature_c", "min"),
            max_temp_c=("temperature_c", "max"),
            rain_days=("rain_flag", "sum"),
            snow_days=("snow_flag", "sum"),
            cold_snap_days=("cold_snap_flag", "sum"),
            heatwave_days=("heatwave_flag", "sum"),
            weather_spike_days=("weather_spike_flag", "sum"),
            temperature_drop_days=("temperature_drop_flag", "sum"),
            temperature_rise_days=("temperature_rise_flag", "sum"),
            payday_window_days=("is_payday_window", "sum"),
            cold_risk_days=("_cold_risk_flag", "sum"),
            heat_risk_days=("_heat_risk_flag", "sum"),
            wet_risk_days=("_wet_risk_flag", "sum"),
            weather_risk_days=("_weather_risk_flag", "sum"),
            business_trigger_days=("_business_trigger_flag", "sum"),
        )
    )

    baseline = historical_baseline(df, horizon=horizon)
    forecast_summary = forecast_summary.merge(baseline, on=["sku", "location_id"], how="left")
    forecast_summary["baseline_21d_units"] = forecast_summary["baseline_21d_units"].fillna(
        forecast_summary["baseline_last_21d_units"].fillna(0)
    )
    forecast_summary["uplift_vs_baseline_percent"] = (
        safe_ratio(forecast_summary["forecast_21d_units"] - forecast_summary["baseline_21d_units"], forecast_summary["baseline_21d_units"]) * 100
    ).round(2)

    if location_scores is not None and not location_scores.empty:
        keep = [
            "sku",
            "location_id",
            "seasonality_score",
            "weather_sensitivity_score",
            "business_impact_score",
        ]
        forecast_summary = forecast_summary.merge(location_scores[keep], on=["sku", "location_id"], how="left")
    for col in ["seasonality_score", "weather_sensitivity_score", "business_impact_score"]:
        if col not in forecast_summary.columns:
            forecast_summary[col] = 0.0
        forecast_summary[col] = forecast_summary[col].fillna(0.0)

    forecast_summary.to_csv(OUT_DIR / "forecast_21d_summary.csv", index=False)

    alert_rows = []
    for _, row in forecast_summary.iterrows():
        reasons = product_trigger_rules(row)
        trigger_days = capped_days(
            row.get(
                "business_trigger_days",
                max_days(
                    row,
                    [
                        "cold_snap_days",
                        "heatwave_days",
                        "weather_spike_days",
                        "rain_days",
                        "snow_days",
                        "payday_window_days",
                    ],
                ),
            )
        )
        weather_risk_days = capped_days(row.get("weather_risk_days", trigger_days))
        uplift = float(row["uplift_vs_baseline_percent"])
        forecast_units = float(row["forecast_21d_units"])
        has_sensitivity_signal = (
            bool(reasons)
            or float(row.get("weather_sensitivity_score", 0)) >= 0.10
            or float(row.get("seasonality_score", 0)) >= 0.40
        )
        is_alert = forecast_units >= 5 and uplift >= 5 and (has_sensitivity_signal or uplift >= 12)
        if not is_alert:
            continue

        if uplift >= 30 or (weather_risk_days >= 10 and uplift >= 15):
            priority = "critical"
        elif uplift >= 12 or weather_risk_days >= 7:
            priority = "high"
        else:
            priority = "medium"

        reason = "; ".join(reasons) if reasons else "forecast peste baseline"
        city = row.get("city", row["location_id"])
        product = row.get("part_name", row["sku"])
        alert_rows.append(
            {
                "location_id": row["location_id"],
                "city": city,
                "country_code": row.get("country_code", ""),
                "sku": row["sku"],
                "part_name": product,
                "category": row.get("category", ""),
                "forecast_21d_units": round(forecast_units, 2),
                "baseline_21d_units": round(float(row["baseline_21d_units"]), 2),
                "uplift_vs_baseline_percent": round(uplift, 2),
                "trigger_days": trigger_days,
                "alert_type": "weather_demand_spike" if weather_risk_days > 0 else "demand_spike",
                "weather_sensitivity_score": round(float(row["weather_sensitivity_score"]), 4),
                "seasonality_score": round(float(row["seasonality_score"]), 4),
                "priority": priority,
                "alert_reason": reason,
                "dealer_message": (
                    f"{city}: {reason}. Pentru {product}, forecastul pe 21 zile este "
                    f"{forecast_units:.0f} buc, cu {uplift:+.0f}% peste ritmul ultimelor 56 zile. "
                    "Verifica stocul, MOQ si lead time."
                ),
            }
        )

    alerts = pd.DataFrame(alert_rows, columns=empty_cols + ["weather_sensitivity_score", "seasonality_score"])
    if not alerts.empty:
        alerts["_rank"] = alerts["priority"].map(PRIORITY_ORDER).fillna(9)
        alerts = alerts.sort_values(["_rank", "uplift_vs_baseline_percent", "forecast_21d_units"], ascending=[True, False, False])
        alerts = alerts.drop(columns="_rank")
    alerts.to_csv(OUT_DIR / "weather_sales_alerts_21d.csv", index=False)
    (OUT_DIR / "weather_sales_alerts_21d.json").write_text(
        json.dumps(alerts.to_dict("records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return alerts, forecast_summary


def create_static_charts(df, scores, location_scores, window_summary, window_by_category, alerts, forecast_summary):
    configure_matplotlib()
    data = df.copy()
    data["month"] = data["date"].dt.month

    if not scores.empty:
        top = scores.head(12).iloc[::-1].copy()
        labels = [short_label(f"{r.part_name} ({r.sku})", 46) for r in top.itertuples()]
        colors = plt.cm.viridis(np.linspace(0.25, 0.85, len(top)))
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.barh(labels, top["business_impact_score"], color=colors)
        ax.set_title("Top produse care merita monitorizate")
        ax.set_xlabel("Business impact score")
        ax.set_ylabel("")
        for i, value in enumerate(top["business_impact_score"]):
            ax.text(value + 0.8, i, f"{value:.1f}", va="center", fontsize=9)
        save_static(fig, "01_product_business_impact.png")

        top_seasonal = scores.nlargest(10, "seasonality_score")["sku"]
        monthly = (
            data[data["sku"].isin(top_seasonal)]
            .groupby(["sku", "month"])["quantity_sold"]
            .mean()
            .unstack(fill_value=0)
            .reindex(columns=range(1, 13), fill_value=0)
        )
        if not monthly.empty:
            indexed = monthly.div(monthly.mean(axis=1).replace(0, np.nan), axis=0).fillna(0)
            label_map = scores.set_index("sku")["part_name"].to_dict()
            ylabels = [short_label(f"{label_map.get(sku, sku)}", 34) for sku in indexed.index]
            fig, ax = plt.subplots(figsize=(12, 6.5))
            im = ax.imshow(indexed.values, aspect="auto", cmap="RdYlGn", vmin=0.3, vmax=max(2.5, indexed.values.max()))
            ax.set_title("Sezonalitate lunara: index vanzari vs media anuala")
            ax.set_xticks(range(12), MONTH_LABELS)
            ax.set_yticks(range(len(ylabels)), ylabels)
            cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
            cbar.set_label("Index sezonier")
            save_static(fig, "02_monthly_seasonality_heatmap.png")

    if not window_summary.empty:
        best = window_summary.loc[window_summary["WAPE_percent"].idxmin()]
        fig, ax = plt.subplots(figsize=(10, 5.5))
        ax.plot(window_summary["window_days"], window_summary["WAPE_percent"], marker="o", linewidth=2.5, color="#1f77b4")
        ax.axvline(best["window_days"], color="#2ca02c", linestyle="--", linewidth=1.5)
        ax.scatter([best["window_days"]], [best["WAPE_percent"]], color="#2ca02c", s=90, zorder=3)
        ax.set_title(f"Diagnostic rolling window: recomandat {int(best['window_days'])} zile")
        ax.set_xlabel("Rolling window (zile)")
        ax.set_ylabel("WAPE % pe ultimele 365 zile")
        ax.set_xticks(window_summary["window_days"])
        save_static(fig, "03_window_selection_wape.png")

    if not window_by_category.empty:
        pivot = window_by_category.pivot(index="category", columns="window_days", values="WAPE_percent").sort_index()
        fig, ax = plt.subplots(figsize=(11, 7))
        im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd")
        ax.set_title("Rolling window pe categorii: WAPE %")
        ax.set_xticks(range(len(pivot.columns)), pivot.columns)
        ax.set_yticks(range(len(pivot.index)), pivot.index)
        for y in range(pivot.shape[0]):
            for x in range(pivot.shape[1]):
                ax.text(x, y, f"{pivot.iloc[y, x]:.0f}", ha="center", va="center", fontsize=8, color="#20242a")
        cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
        cbar.set_label("WAPE %")
        save_static(fig, "04_window_by_category_heatmap.png")

    if not location_scores.empty:
        top_pairs = location_scores.head(80)
        top_skus = top_pairs.groupby("sku")["business_impact_score"].max().nlargest(10).index
        heat = (
            top_pairs[top_pairs["sku"].isin(top_skus)]
            .pivot_table(index="sku", columns="city", values="avg_daily_sales", aggfunc="mean")
            .fillna(0)
        )
        if not heat.empty:
            labels = location_scores.drop_duplicates("sku").set_index("sku")["part_name"].to_dict()
            ylabels = [short_label(labels.get(sku, sku), 34) for sku in heat.index]
            fig, ax = plt.subplots(figsize=(13, 6.5))
            im = ax.imshow(heat.values, aspect="auto", cmap="Blues")
            ax.set_title("Vanzari medii zilnice pe produs si locatie")
            ax.set_xticks(range(len(heat.columns)), heat.columns, rotation=35, ha="right")
            ax.set_yticks(range(len(ylabels)), ylabels)
            cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
            cbar.set_label("Buc / zi")
            save_static(fig, "05_sales_by_location_heatmap.png")

        effects = build_weather_trigger_effects(data)
        if not effects.empty:
            top_effects = effects[effects["uplift_percent"] > 0].head(10).iloc[::-1].copy()
            if not top_effects.empty:
                labels = [
                    short_label(f"{row.part_name} | {row.trigger_label}", 52)
                    for row in top_effects.itertuples()
                ]
                colors = plt.cm.Set2(np.linspace(0.05, 0.95, top_effects["trigger_label"].nunique()))
                color_lookup = dict(zip(top_effects["trigger_label"].drop_duplicates(), colors))
                fig, ax = plt.subplots(figsize=(13, 7))
                bars = ax.barh(
                    labels,
                    top_effects["uplift_percent"],
                    color=[color_lookup[label] for label in top_effects["trigger_label"]],
                    edgecolor="white",
                    linewidth=0.8,
                )
                ax.set_title("Uplift istoric meteo, controlat pe acelasi sezon")
                ax.set_xlabel("Uplift vs zile fara trigger din aceleasi luni (%)")
                ax.set_ylabel("")
                xmax = max(40, float(top_effects["uplift_percent"].quantile(0.95)) * 1.18)
                ax.set_xlim(0, xmax)
                for bar, row in zip(bars, top_effects.itertuples()):
                    ax.text(
                        bar.get_width() + xmax * 0.015,
                        bar.get_y() + bar.get_height() / 2,
                        f"{row.uplift_percent:.0f}% | n={row.trigger_days}",
                        va="center",
                        fontsize=8.5,
                    )
                legend_handles = [
                    Patch(facecolor=color_lookup[label], label=label)
                    for label in color_lookup
                ]
                ax.legend(handles=legend_handles, loc="lower right", fontsize=8, frameon=True, title="Trigger")
                save_static(fig, "06_weather_trigger_uplift.png")

    if forecast_summary is not None and not forecast_summary.empty:
        show = forecast_summary[forecast_summary["uplift_vs_baseline_percent"] >= 2].copy()
        if show.empty:
            show = forecast_summary.nlargest(40, "uplift_vs_baseline_percent").copy()
        top_skus = show.groupby("sku")["uplift_vs_baseline_percent"].max().nlargest(10).index
        heat = (
            show[show["sku"].isin(top_skus)]
            .pivot_table(index="sku", columns="city", values="uplift_vs_baseline_percent", aggfunc="max")
            .fillna(np.nan)
        )
        if not heat.empty:
            labels = forecast_summary.drop_duplicates("sku").set_index("sku")["part_name"].to_dict()
            fig_height = max(3.2, 1.1 * len(heat.index) + 1.8)
            fig, ax = plt.subplots(figsize=(13, fig_height))
            values = heat.values.astype(float)
            finite = values[np.isfinite(values)]
            vmax = max(5.0, float(np.nanpercentile(finite, 95)) if len(finite) else 5.0)
            cmap = plt.cm.YlOrRd.copy()
            cmap.set_bad("#f1f5f9")
            im = ax.imshow(np.ma.masked_invalid(values), aspect="auto", cmap=cmap, vmin=0, vmax=vmax)
            ax.set_title("Forecast 21 zile: locatii cu uplift pozitiv estimat")
            ax.set_xticks(range(len(heat.columns)), heat.columns, rotation=35, ha="right")
            ax.set_yticks(range(len(heat.index)), [short_label(labels.get(sku, sku), 34) for sku in heat.index])
            ax.grid(False)
            for y in range(heat.shape[0]):
                for x in range(heat.shape[1]):
                    val = heat.iloc[y, x]
                    if pd.notna(val) and val >= 2:
                        text_color = "white" if val >= vmax * 0.55 else "#20242a"
                        ax.text(x, y, f"{val:.0f}%", ha="center", va="center", fontsize=8, color=text_color)
            cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
            cbar.set_label("Uplift %")
            save_static(fig, "07_forecast_uplift_heatmap.png")

    if alerts is not None and not alerts.empty:
        top_alerts = alerts[alerts["uplift_vs_baseline_percent"] > 0].head(12).iloc[::-1].copy()
        if top_alerts.empty:
            top_alerts = alerts.head(12).iloc[::-1].copy()
        labels = [short_label(f"{r.city} - {r.part_name}", 52) for r in top_alerts.itertuples()]
        color_map = {"critical": "#d62728", "high": "#ff7f0e", "medium": "#2ca02c"}
        colors = top_alerts["priority"].map(color_map).fillna("#1f77b4")
        fig_height = max(3.5, 1.2 + len(top_alerts) * 0.85)
        fig, ax = plt.subplots(figsize=(13, fig_height))
        ax.barh(labels, top_alerts["uplift_vs_baseline_percent"], color=colors)
        ax.axvline(0, color="#667085", linewidth=1.0)
        ax.set_title("Alerte dealer: spike real estimat in urmatoarele 21 zile")
        ax.set_xlabel("Uplift vs baseline (%)")
        xmax = max(5.0, float(top_alerts["uplift_vs_baseline_percent"].max()) * 1.22)
        ax.set_xlim(0, xmax)
        ax.grid(axis="y", visible=False)
        for i, row in enumerate(top_alerts.itertuples()):
            x_text = min(row.uplift_vs_baseline_percent + xmax * 0.025, xmax * 0.98)
            ax.text(
                x_text,
                i,
                f"{row.priority} | {row.forecast_21d_units:.0f} buc",
                va="center",
                fontsize=9,
            )
        save_static(fig, "08_dealer_alerts_21d.png")

        forecast_path = PROCESSED_DIR / "forecast_30d.csv"
        if forecast_path.exists():
            fc = pd.read_csv(forecast_path, parse_dates=["forecast_date"])
            fc = add_forecast_flags(fc)
            pred_col = first_existing(fc.columns, ["predicted_quantity", "forecast_quantity", "prediction", "yhat", "quantity_forecast"])
            if pred_col is None:
                return
            fc = fc[fc["horizon_day"] <= HORIZON_DAYS]
            selected = alerts.head(4)[["sku", "location_id"]].drop_duplicates()
            alert_lookup = alerts.drop_duplicates(["sku", "location_id"]).set_index(["sku", "location_id"]).to_dict(orient="index")
            panel_count = len(selected)
            cols = 2 if panel_count > 1 else 1
            rows = max(1, int(np.ceil(panel_count / cols)))
            fig_width = 15.5 if cols == 2 else 8.5
            fig_height = rows * 4.4 + 1.4
            fig = plt.figure(figsize=(fig_width, fig_height))
            grid = fig.add_gridspec(
                rows * 2,
                cols,
                height_ratios=[ratio for _ in range(rows) for ratio in (3.0, 1.05)],
                hspace=0.42,
                wspace=0.26,
            )
            trigger_cols = [
                c
                for c in ["cold_snap_flag", "heatwave_flag", "weather_spike_flag", "temperature_drop_flag", "temperature_rise_flag"]
                if c in fc.columns
            ]

            def shade_triggers(sales_ax, temp_ax, part_frame):
                if not trigger_cols:
                    return
                flags = part_frame[trigger_cols].max(axis=1).astype(bool).tolist()
                dates = part_frame["forecast_date"].tolist()
                start = None
                end = None
                for flag, current_date in zip(flags + [False], dates + [None]):
                    if flag and start is None:
                        start = current_date
                    if flag:
                        end = current_date
                    if not flag and start is not None:
                        left = start - pd.Timedelta(hours=12)
                        right = end + pd.Timedelta(hours=12)
                        for target_ax in [sales_ax, temp_ax]:
                            target_ax.axvspan(left, right, color="#f59e0b", alpha=0.10, linewidth=0, zorder=0)
                        start = None
                        end = None

            for idx in range(rows * cols):
                grid_row = (idx // cols) * 2
                grid_col = idx % cols
                ax = fig.add_subplot(grid[grid_row, grid_col])
                temp_ax = fig.add_subplot(grid[grid_row + 1, grid_col], sharex=ax)
                if idx >= len(selected):
                    ax.axis("off")
                    temp_ax.axis("off")
                    continue
                row = selected.iloc[idx]
                part = fc[(fc["sku"] == row.sku) & (fc["location_id"] == row.location_id)].sort_values("forecast_date")
                if part.empty:
                    ax.axis("off")
                    temp_ax.axis("off")
                    continue
                label = short_label(f"{part['city'].iloc[0]} - {part['part_name'].iloc[0]}", 46)
                y = part[pred_col].astype(float).clip(lower=0)
                dates = part["forecast_date"]
                x_num = mdates.date2num(dates)
                trend = y.rolling(7, min_periods=2).mean()
                band_pct = float(np.clip(0.12 + safe_ratio(y.std(ddof=0), max(y.mean(), 1e-6)) * 0.20, 0.14, 0.28))
                lower = (y * (1 - band_pct)).clip(lower=0)
                upper = y * (1 + band_pct)
                info = alert_lookup.get((row.sku, row.location_id), {})
                baseline_units = float(info.get("baseline_21d_units", np.nan))
                baseline_daily = baseline_units / HORIZON_DAYS if np.isfinite(baseline_units) and baseline_units > 0 else np.nan
                forecast_units = float(info.get("forecast_21d_units", y.sum()))
                uplift = float(info.get("uplift_vs_baseline_percent", safe_ratio(forecast_units - baseline_units, baseline_units) * 100 if np.isfinite(baseline_units) and baseline_units > 0 else 0))

                shade_triggers(ax, temp_ax, part)
                ax.fill_between(x_num, lower, upper, color="#1f77b4", alpha=0.13, linewidth=0, zorder=1)
                ax.plot(dates, y, marker="o", color="#1f77b4", linewidth=2.2, markersize=4.5, zorder=3)
                ax.plot(dates, trend, color="#0f4c81", linestyle="--", linewidth=1.7, zorder=4)
                if np.isfinite(baseline_daily):
                    ax.axhline(baseline_daily, color="#6b7280", linestyle=":", linewidth=1.8, zorder=2)
                ax.set_title(label, fontsize=10, fontweight="bold")
                ax.set_ylabel("Forecast buc/zi")
                ax.tick_params(axis="x", labelbottom=False)
                ax.margins(x=0.02)
                ax.text(
                    0.98,
                    0.94,
                    f"21 zile: {forecast_units:.0f} buc\nvs baseline: {uplift:+.0f}%",
                    transform=ax.transAxes,
                    ha="right",
                    va="top",
                    fontsize=8.5,
                    bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#d0d7e2", "alpha": 0.94},
                )

                temp_ax.plot(dates, part["temperature_c"], color="#d62728", linewidth=1.9)
                temp_ax.axhline(0, color="#d62728", alpha=0.35, linewidth=0.9)
                temp_ax.set_ylabel("Temp C")
                temp_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
                temp_ax.tick_params(axis="x", rotation=25)
                temp_ax.margins(x=0.02)
            fig.suptitle("Forecast zilnic 21 zile pentru cele mai importante alerte", fontweight="bold")
            legend_items = [
                Line2D([0], [0], color="#1f77b4", marker="o", linewidth=2, label="Forecast vanzari (buc/zi)"),
                Line2D([0], [0], color="#0f4c81", linestyle="--", linewidth=1.8, label="Trend forecast 7 zile"),
                Line2D([0], [0], color="#6b7280", linestyle=":", linewidth=1.8, label="Baseline zilnic"),
                Patch(facecolor="#1f77b4", alpha=0.13, label="Interval scenariu"),
                Patch(facecolor="#f59e0b", alpha=0.12, label="Fereastra trigger meteo"),
                Line2D([0], [0], color="#d62728", linewidth=1.8, label="Temperatura forecast (C)"),
            ]
            fig.legend(
                handles=legend_items,
                loc="lower center",
                bbox_to_anchor=(0.5, 0.005),
                ncol=3,
                frameon=False,
                fontsize=8.5,
            )
            fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.18)
            path = STATIC_CHART_DIR / "09_forecast_21d_alert_examples.png"
            fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            print(f"saved: {path}")


def most_volatile_product_locations(location_scores, limit=4):
    if location_scores is None or location_scores.empty:
        return pd.DataFrame()
    needed = {"sku", "location_id", "volatility_score", "part_name", "city"}
    if not needed.issubset(location_scores.columns):
        return pd.DataFrame()
    ranked = location_scores.sort_values(
        ["volatility_score", "seasonality_score", "weather_sensitivity_score", "business_impact_score"],
        ascending=False,
    )
    return ranked.drop_duplicates("sku").head(limit).copy()


def plot_product_location_forecast(ax, daily, fc_daily, title, show_legend=False, compact=False):
    hist_color = "#2f6f9f"
    actual_color = "#9fb6cf"
    forecast_color = "#f28e2b"
    reference_color = "#6b7280"
    temp_color = "#c0392b"

    forecast_start = fc_daily["forecast_date"].min()
    forecast_end = fc_daily["forecast_date"].max()
    ax.axvspan(forecast_start, forecast_end, color="#fff3e6", alpha=0.8, zorder=0)
    ax.axvline(forecast_start, color="#667085", linestyle="--", linewidth=1.2, zorder=3)

    ax.plot(
        daily["date"],
        daily["quantity_sold"],
        color=actual_color,
        alpha=0.42,
        linewidth=1.0,
        label="Vanzari zilnice",
        zorder=1,
    )
    ax.plot(
        daily["date"],
        daily["rolling_28"],
        color=hist_color,
        linewidth=2.6,
        label="Trend istoric 28 zile",
        zorder=4,
    )
    if "same_period_last_year" in fc_daily.columns and fc_daily["same_period_last_year"].notna().any():
        ax.plot(
            fc_daily["forecast_date"],
            fc_daily["same_period_last_year"],
            color=reference_color,
            linestyle=":",
            linewidth=2.0,
            label="Aceeasi perioada anul trecut",
            zorder=3,
        )

    x_fc = mdates.date2num(fc_daily["forecast_date"])
    ax.fill_between(
        x_fc,
        0,
        fc_daily["predicted_quantity"],
        color=forecast_color,
        alpha=0.18,
        linewidth=0,
        label="Zona forecast",
        zorder=2,
    )
    ax.plot(
        fc_daily["forecast_date"],
        fc_daily["predicted_quantity"],
        color=forecast_color,
        marker="o",
        markersize=4 if compact else 5,
        linewidth=2.4,
        label="Forecast zilnic",
        zorder=5,
    )

    trigger_cols = [c for c in ["heatwave_flag", "weather_spike_flag"] if c in fc_daily.columns]
    if trigger_cols:
        trigger_mask = fc_daily[trigger_cols].max(axis=1) > 0
        if trigger_mask.any():
            ax.scatter(
                fc_daily.loc[trigger_mask, "forecast_date"],
                fc_daily.loc[trigger_mask, "predicted_quantity"],
                s=42 if not compact else 28,
                color="#d62728",
                edgecolor="white",
                linewidth=0.7,
                label="Trigger meteo",
                zorder=6,
            )

    ax.set_title(title, fontsize=10 if compact else 12, fontweight="bold", loc="left", pad=10)
    ax.set_xlabel("")
    ax.set_ylabel("Unitati / zi")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", rotation=25)
    ax.margins(x=0.01)

    ymax_candidates = [
        daily["quantity_sold"].quantile(0.98),
        daily["rolling_28"].max(),
        fc_daily["predicted_quantity"].max(),
    ]
    if "same_period_last_year" in fc_daily.columns:
        ymax_candidates.append(fc_daily["same_period_last_year"].max())
    ymax = max([float(v) for v in ymax_candidates if pd.notna(v)] + [1.0])
    ax.set_ylim(0, ymax * 1.22)

    if not compact and "temperature_c" in fc_daily.columns:
        ax2 = ax.twinx()
        ax2.plot(fc_daily["forecast_date"], fc_daily["temperature_c"], color=temp_color, linewidth=2.0, alpha=0.85, label="Temp forecast")
        ax2.axhline(0, color=temp_color, linewidth=0.9, alpha=0.35)
        temp_min = float(fc_daily["temperature_c"].min())
        temp_max = float(fc_daily["temperature_c"].max())
        temp_pad = max(2.5, (temp_max - temp_min) * 0.25)
        ax2.set_ylim(min(temp_min - temp_pad, -5), max(temp_max + temp_pad, 5))
        ax2.set_ylabel("Temp C", color=temp_color)
        ax2.tick_params(axis="y", labelcolor=temp_color)
        ax2.spines["right"].set_color("#f2b8b5")
    else:
        ax2 = None

    forecast_total = float(fc_daily["predicted_quantity"].sum())
    baseline_total = float(daily["rolling_28"].dropna().tail(1).iloc[0] * len(fc_daily)) if daily["rolling_28"].notna().any() else 0.0
    delta = safe_ratio(forecast_total - baseline_total, baseline_total) * 100 if baseline_total > 0 else 0.0
    cold_days = int(fc_daily["cold_snap_flag"].sum()) if "cold_snap_flag" in fc_daily.columns else 0
    summary = f"Forecast 21z: {forecast_total:.0f} buc\nvs trend 28z: {delta:+.0f}%"
    if cold_days:
        summary += f"\nZile cold snap: {cold_days}/{len(fc_daily)}"
    ax.text(
        0.985,
        0.96,
        summary,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8 if compact else 9,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#d0d7e2", "alpha": 0.94},
        zorder=10,
    )

    if show_legend:
        handles, labels = ax.get_legend_handles_labels()
        if ax2 is not None:
            h2, l2 = ax2.get_legend_handles_labels()
            handles += h2
            labels += l2
        if compact:
            ax.legend(handles, labels, loc="upper left", ncol=2, frameon=True, fontsize=7)
        else:
            ax.legend(
                handles,
                labels,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.16),
                ncol=4,
                frameon=False,
                fontsize=8,
            )


def build_product_location_series(df, forecast, pred_col, sku, location_id):
    history = df[(df["sku"] == sku) & (df["location_id"] == location_id)].copy()
    if history.empty:
        return pd.DataFrame(), pd.DataFrame()

    agg_spec = {"quantity_sold": "sum"}
    if "temperature_c" in history.columns:
        agg_spec["temperature_c"] = "mean"
    for col in ["cold_snap_flag", "heatwave_flag", "weather_spike_flag"]:
        if col in history.columns:
            agg_spec[col] = "max"
    all_daily = history.groupby("date", as_index=False).agg(agg_spec).sort_values("date")
    daily = all_daily[all_daily["date"] >= all_daily["date"].max() - pd.Timedelta(days=180)].copy()
    daily["rolling_28"] = daily["quantity_sold"].rolling(28, min_periods=7).mean()

    fc = forecast[
        (forecast["sku"] == sku)
        & (forecast["location_id"] == location_id)
        & (forecast["horizon_day"] <= HORIZON_DAYS)
    ].copy()
    if fc.empty:
        return daily, pd.DataFrame()
    fc_agg = {pred_col: "sum"}
    for col in ["temperature_c", "rain_mm", "snow_cm"]:
        if col in fc.columns:
            fc_agg[col] = "mean"
    for col in ["cold_snap_flag", "heatwave_flag", "weather_spike_flag", "is_payday_window"]:
        if col in fc.columns:
            fc_agg[col] = "max"
    fc_daily = fc.groupby("forecast_date", as_index=False).agg(fc_agg).sort_values("forecast_date").rename(columns={pred_col: "predicted_quantity"})
    fc_daily["forecast_trend_7"] = fc_daily["predicted_quantity"].rolling(7, min_periods=2).mean()
    fc_daily["reference_date"] = fc_daily["forecast_date"] - pd.DateOffset(years=1)
    reference = all_daily[["date", "quantity_sold"]].rename(
        columns={"date": "reference_date", "quantity_sold": "same_period_last_year"}
    )
    fc_daily = fc_daily.merge(reference, on="reference_date", how="left")
    return daily, fc_daily


def save_legacy(fig, name):
    path = LEGACY_PLOT_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved: {path}")


def refresh_legacy_sales_summary_plots(df, scores, location_scores):
    configure_matplotlib()

    if location_scores is not None and not location_scores.empty:
        required = {"sku", "location_id", "part_name", "city", "volatility_score", "seasonality_score", "weather_sensitivity_score"}
        if required.issubset(location_scores.columns):
            ranked = (
                location_scores.sort_values(
                    ["volatility_score", "business_impact_score", "seasonality_score"],
                    ascending=False,
                )
                .drop_duplicates("sku")
                .head(12)
                .iloc[::-1]
                .copy()
            )
            labels = [short_label(f"{row.part_name} | {row.city}", 54) for row in ranked.itertuples()]
            fig, ax = plt.subplots(figsize=(12, 7))
            bars = ax.barh(labels, ranked["volatility_score"], color="#2f6f9f")
            ax.set_title("Outlieri de vanzari: produsul in locatia cu volatilitatea maxima")
            ax.set_xlabel("Volatilitate zilnica (CV)")
            ax.set_ylabel("")
            for bar, row in zip(bars, ranked.itertuples()):
                ax.text(
                    bar.get_width() + 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    f"sez {row.seasonality_score:.1f} | meteo {row.weather_sensitivity_score:.1f}",
                    va="center",
                    fontsize=8.5,
                )
            save_legacy(fig, "01_top_volatile_products.png")

    if scores is not None and not scores.empty:
        top_skus = scores.nlargest(10, "seasonality_score")["sku"]
        monthly = (
            df[df["sku"].isin(top_skus)]
            .assign(month=lambda x: x["date"].dt.month)
            .groupby(["sku", "month"])["quantity_sold"]
            .mean()
            .unstack(fill_value=0)
            .reindex(columns=range(1, 13), fill_value=0)
        )
        if not monthly.empty:
            indexed = monthly.div(monthly.mean(axis=1).replace(0, np.nan), axis=0).fillna(0)
            label_map = scores.set_index("sku")["part_name"].to_dict()
            fig, ax = plt.subplots(figsize=(12, 6.5))
            vmax = max(2.0, float(np.nanpercentile(indexed.values, 95)))
            im = ax.imshow(indexed.values, aspect="auto", cmap="RdYlGn", vmin=0.35, vmax=vmax)
            ax.set_title("Produse sensibile la sezonalitate: index lunar vs media anuala")
            ax.set_xticks(range(12), MONTH_LABELS)
            ax.set_yticks(range(len(indexed.index)), [short_label(label_map.get(sku, sku), 36) for sku in indexed.index])
            cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
            cbar.set_label("Index sezonier")
            save_legacy(fig, "02_seasonality.png")

    effects = build_weather_trigger_effects(df)
    if not effects.empty:
        top_effects = effects[effects["uplift_percent"] > 0].head(8).iloc[::-1].copy()
        if not top_effects.empty:
            labels = [short_label(f"{row.part_name} | {row.trigger_label}", 54) for row in top_effects.itertuples()]
            fig, ax = plt.subplots(figsize=(12, 6.5))
            bars = ax.barh(labels, top_effects["uplift_percent"], color="#5aa469")
            ax.set_title("Produse sensibile la vreme: uplift controlat pe sezon")
            ax.set_xlabel("Uplift vs zile fara trigger din aceleasi luni (%)")
            ax.set_ylabel("")
            xmax = max(35, float(top_effects["uplift_percent"].max()) * 1.20)
            ax.set_xlim(0, xmax)
            for bar, row in zip(bars, top_effects.itertuples()):
                ax.text(
                    bar.get_width() + xmax * 0.015,
                    bar.get_y() + bar.get_height() / 2,
                    f"{row.uplift_percent:.0f}% | n={row.trigger_days}",
                    va="center",
                    fontsize=8.5,
                )
            save_legacy(fig, "05_weather_sensitive.png")


def refresh_legacy_temp_vs_sales_plot(df):
    needed = {"temperature_c", "quantity_sold"}
    if not needed.issubset(df.columns):
        return

    data = df.copy()
    battery = data[data["category"].astype(str).str.lower().eq("battery")].copy() if "category" in data.columns else pd.DataFrame()
    if battery.empty:
        sku_mask = data["sku"].astype(str).str.contains("BATT|BATTERY", case=False, regex=True) if "sku" in data.columns else False
        name_mask = data["part_name"].astype(str).str.contains("bater|battery", case=False, regex=True) if "part_name" in data.columns else False
        battery = data[sku_mask | name_mask].copy()
    if battery.empty:
        return

    battery["temperature_c"] = pd.to_numeric(battery["temperature_c"], errors="coerce")
    battery["quantity_sold"] = pd.to_numeric(battery["quantity_sold"], errors="coerce")
    battery = battery.dropna(subset=["temperature_c", "quantity_sold"])
    if battery.empty:
        return

    daily = (
        battery.groupby(["date", "city"], as_index=False)
        .agg(
            temperature_c=("temperature_c", "mean"),
            quantity_sold=("quantity_sold", "sum"),
            cold_snap_flag=("cold_snap_flag", "max") if "cold_snap_flag" in battery.columns else ("quantity_sold", "size"),
        )
        .sort_values("temperature_c")
    )
    bins = np.arange(np.floor(daily["temperature_c"].min() / 5) * 5, np.ceil(daily["temperature_c"].max() / 5) * 5 + 5, 5)
    if len(bins) < 3:
        bins = np.linspace(daily["temperature_c"].min(), daily["temperature_c"].max(), 6)
    daily["temp_bin"] = pd.cut(daily["temperature_c"], bins=bins, include_lowest=True)
    binned = (
        daily.groupby("temp_bin", observed=True)
        .agg(
            temp_mid=("temperature_c", "mean"),
            avg_sales=("quantity_sold", "mean"),
            p75_sales=("quantity_sold", lambda s: float(np.percentile(s, 75))),
            n_days=("quantity_sold", "size"),
        )
        .reset_index()
        .dropna(subset=["temp_mid", "avg_sales"])
    )

    configure_matplotlib()
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    sample = daily.sample(min(len(daily), 2500), random_state=42)
    city_counts = sample["city"].nunique()
    scatter = ax.scatter(
        sample["temperature_c"],
        sample["quantity_sold"],
        c=pd.factorize(sample["city"])[0] if city_counts > 1 else "#9fb6cf",
        cmap="tab20",
        alpha=0.20,
        s=20,
        linewidth=0,
        label="Zile locatie",
    )
    ax.plot(
        binned["temp_mid"],
        binned["avg_sales"],
        color="#1f77b4",
        marker="o",
        linewidth=2.6,
        label="Medie pe interval temperatura",
    )
    ax.plot(
        binned["temp_mid"],
        binned["p75_sales"],
        color="#f28e2b",
        marker="o",
        linewidth=2.0,
        linestyle="--",
        label="P75 pe interval temperatura",
    )
    ax.axvspan(daily["temperature_c"].min(), 0, color="#dbeafe", alpha=0.45, label="Zona rece")
    ax.axvline(0, color="#64748b", linestyle="--", linewidth=1.1)

    cold = daily[daily["temperature_c"] <= 0]["quantity_sold"].mean()
    warm = daily[daily["temperature_c"] > 10]["quantity_sold"].mean()
    uplift = safe_ratio(cold - warm, warm) * 100 if pd.notna(cold) and pd.notna(warm) and warm > 0 else 0.0
    total_units = int(battery["quantity_sold"].sum())
    summary = f"Battery sales\nTotal: {total_units:,} buc\nSub 0C vs >10C: {uplift:+.0f}%".replace(",", ".")
    ax.text(
        0.98,
        0.96,
        summary,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#d0d7e2", "alpha": 0.95},
    )

    ax.set_title("Temperatura vs vanzari - baterii", loc="left", fontsize=14, fontweight="bold")
    ax.set_xlabel("Temperatura medie zilnica (C)")
    ax.set_ylabel("Unitati vandute / zi / locatie")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, frameon=False, fontsize=9)
    ax.margins(x=0.02)
    fig.tight_layout()
    path = LEGACY_PLOT_DIR / "03_temp_vs_sales.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved: {path}")


def refresh_legacy_forecast_plot(df, location_scores):
    forecast_path = PROCESSED_DIR / "forecast_30d.csv"
    selected = most_volatile_product_locations(location_scores, limit=4)
    if not forecast_path.exists() or selected.empty:
        return

    forecast = pd.read_csv(forecast_path, parse_dates=["forecast_date"])
    pred_col = first_existing(forecast.columns, ["predicted_quantity", "forecast_quantity", "prediction", "yhat"])
    if pred_col is None:
        return

    configure_matplotlib()

    plot_items = []
    selected_rows = []
    for row in selected.itertuples():
        daily, fc_daily = build_product_location_series(df, forecast, pred_col, row.sku, row.location_id)
        if daily.empty or fc_daily.empty:
            continue
        title = (
            f"{short_label(row.part_name, 36)} | {row.city} "
            f"(vol={row.volatility_score:.2f})"
        )
        plot_items.append((daily, fc_daily, title, row))
        selected_rows.append(
            {
                "sku": row.sku,
                "location_id": row.location_id,
                "part_name": row.part_name,
                "city": row.city,
                "volatility_score": row.volatility_score,
                "seasonality_score": row.seasonality_score,
                "weather_sensitivity_score": row.weather_sensitivity_score,
            }
        )

        fig, ax = plt.subplots(figsize=(11, 5.6))
        plot_product_location_forecast(ax, daily, fc_daily, title, show_legend=True)
        single_path = OUTLIER_FORECAST_DIR / f"{row.sku}_{row.location_id}_forecast_21d.png"
        fig.tight_layout()
        fig.savefig(single_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"saved: {single_path}")

    if not plot_items:
        return

    pd.DataFrame(selected_rows).to_csv(OUT_DIR / "outlier_forecast_product_locations.csv", index=False)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=False)
    axes = axes.flatten()
    for idx, (daily, fc_daily, title, _row) in enumerate(plot_items):
        plot_product_location_forecast(axes[idx], daily, fc_daily, title, show_legend=(idx == 0), compact=True)
    for ax in axes[len(plot_items) :]:
        ax.axis("off")
    fig.suptitle("Forecast 21 zile pentru produse outlier in locatia cu volatilitatea maxima", fontweight="bold", fontsize=15)
    save_static(fig, "10_outlier_forecast_by_product_location.png")

    legacy_path = LEGACY_PLOT_DIR / "04_forecast.png"
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=False)
    axes = axes.flatten()
    for idx, (daily, fc_daily, title, _row) in enumerate(plot_items):
        plot_product_location_forecast(axes[idx], daily, fc_daily, title, show_legend=(idx == 0), compact=True)
    for ax in axes[len(plot_items) :]:
        ax.axis("off")
    fig.suptitle("Forecast 21 zile pentru produse outlier in locatia cu volatilitatea maxima", fontweight="bold", fontsize=15)
    fig.tight_layout()
    fig.savefig(legacy_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved: {legacy_path}")


def create_interactive_charts(df, scores, location_scores, window_summary, alerts, forecast_summary):
    if not scores.empty:
        top = scores.head(15).copy()
        top["label"] = top["sku"] + " - " + top["part_name"]
        fig = px.bar(
            top,
            x="business_impact_score",
            y="label",
            orientation="h",
            color="weather_sensitivity_score",
            hover_data=["category", "seasonality_score", "volatility_score", "business_explanation"],
            title="Top produse pentru monitorizare comerciala",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        fig.write_html(CHART_DIR / "01_product_business_impact.html")

        fig = px.scatter(
            scores,
            x="seasonality_score",
            y="weather_sensitivity_score",
            size="revenue_proxy_eur",
            color="category",
            hover_name="sku",
            hover_data=["part_name", "business_impact_score", "volatility_score", "business_explanation"],
            title="Sezonalitate vs sensibilitate la vreme",
        )
        fig.write_html(CHART_DIR / "02_seasonality_vs_weather_sensitivity.html")

    if not window_summary.empty:
        fig = px.line(
            window_summary,
            x="window_days",
            y="WAPE_percent",
            markers=True,
            hover_data=["MAE", "rows_evaluated"],
            title="Alegerea rolling window pentru baseline/forecast",
        )
        fig.write_html(CHART_DIR / "03_window_selection.html")

    if not location_scores.empty:
        top_pairs = location_scores.head(150).copy()
        heat = top_pairs.pivot_table(
            index="part_name",
            columns="city",
            values="avg_daily_sales",
            aggfunc="mean",
        ).fillna(0)
        fig = px.imshow(heat, aspect="auto", title="Vanzari medii zilnice pe produs si locatie")
        fig.write_html(CHART_DIR / "04_sales_heatmap_product_location.html")

    if forecast_summary is not None and not forecast_summary.empty:
        show = forecast_summary[forecast_summary["uplift_vs_baseline_percent"] >= 2].copy()
        if show.empty:
            show = forecast_summary.nlargest(80, "uplift_vs_baseline_percent").copy()
        heat = show.pivot_table(
            index="part_name",
            columns="city",
            values="uplift_vs_baseline_percent",
            aggfunc="max",
        ).fillna(0)
        fig = px.imshow(
            heat,
            aspect="auto",
            color_continuous_scale="YlOrRd",
            zmin=0,
            title="Forecast 21 zile: locatii cu uplift pozitiv estimat",
        )
        fig.write_html(CHART_DIR / "05_forecast_uplift_heatmap.html")

    if alerts is not None and not alerts.empty:
        alert_show = alerts[alerts["uplift_vs_baseline_percent"] > 0].head(40).copy()
        if alert_show.empty:
            alert_show = alerts.head(40).copy()
        fig = px.bar(
            alert_show,
            x="uplift_vs_baseline_percent",
            y="part_name",
            color="priority",
            facet_col="city",
            facet_col_wrap=4,
            hover_data=["sku", "location_id", "forecast_21d_units", "baseline_21d_units", "trigger_days", "alert_reason", "dealer_message"],
            title="Alerte dealer: spike real estimat in urmatoarele 21 zile",
        )
        fig.write_html(CHART_DIR / "06_weather_alerts_21d.html")

        table = alert_show.head(20)
        fig = go.Figure(
            data=[
                go.Table(
                    header=dict(values=["Prioritate", "Locatie", "Produs", "Uplift %", "Mesaj dealer"]),
                    cells=dict(
                        values=[
                            table["priority"],
                            table["city"],
                            table["part_name"],
                            table["uplift_vs_baseline_percent"],
                            table["dealer_message"],
                        ]
                    ),
                )
            ]
        )
        fig.update_layout(title="Explainability alerte")
        fig.write_html(CHART_DIR / "07_alerts_explainability_table.html")


def main():
    df = load_sales_data()
    scores = compute_business_impact_scores(df)
    location_scores = compute_product_location_scores(df)
    window_summary, window_by_category = compute_window_diagnostics(df)
    alerts, forecast_summary = generate_weather_sales_alerts(df, location_scores)
    create_static_charts(df, scores, location_scores, window_summary, window_by_category, alerts, forecast_summary)
    refresh_legacy_sales_summary_plots(df, scores, location_scores)
    refresh_legacy_temp_vs_sales_plot(df)
    refresh_legacy_forecast_plot(df, location_scores)
    create_interactive_charts(df, scores, location_scores, window_summary, alerts, forecast_summary)

    best = window_summary.loc[window_summary["WAPE_percent"].idxmin()] if not window_summary.empty else None
    print("Generated outputs:")
    print(f"- {OUT_DIR / 'business_impact_scores.csv'}")
    print(f"- {OUT_DIR / 'product_location_scores.csv'}")
    print(f"- {OUT_DIR / 'window_diagnostics_summary.csv'}")
    print(f"- {OUT_DIR / 'forecast_21d_summary.csv'}")
    print(f"- {OUT_DIR / 'weather_sales_alerts_21d.csv'} ({len(alerts)} alerts)")
    print(f"- {STATIC_CHART_DIR}")
    print(f"- {CHART_DIR}")
    if best is not None:
        print(f"Recommended rolling window: {int(best['window_days'])} days (WAPE={best['WAPE_percent']:.2f}%)")


if __name__ == "__main__":
    main()
