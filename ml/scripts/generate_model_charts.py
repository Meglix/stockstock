from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "scripts" else Path.cwd()
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUT = DATA_PROCESSED / "charts"
OUT.mkdir(parents=True, exist_ok=True)


def configure():
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


def first_existing(columns, candidates):
    for col in candidates:
        if col in columns:
            return col
    return None


def short_label(value, width=44):
    text = str(value)
    return text if len(text) <= width else text[: width - 3] + "..."


def savefig(name: str):
    path = OUT / name
    plt.tight_layout()
    plt.savefig(path, dpi=170, bbox_inches="tight", facecolor=plt.gcf().get_facecolor())
    plt.close()
    print(f"saved: {path}")


def chart_metrics():
    metrics_path = DATA_PROCESSED / "model_metrics.json"
    if not metrics_path.exists():
        return
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    # Supports both flat and nested metric formats.
    model = data.get("model", data.get("ExtraTreesRegressor", data))
    baseline = data.get("baseline", data.get("Baseline rolling mean 14", {}))
    metric_names = ["MAE", "RMSE", "MAPE_percent", "WAPE_percent"]
    rows = []
    for metric in metric_names:
        if metric in model:
            rows.append({"metric": metric, "series": "ML model", "value": model[metric]})
        if metric in baseline:
            rows.append({"metric": metric, "series": "Baseline", "value": baseline[metric]})
    if not rows:
        return
    configure()
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="metric", columns="series", values="value")
    ax = pivot.plot(kind="bar", figsize=(9, 5))
    ax.set_title("Forecast model vs baseline")
    ax.set_ylabel("Metric value")
    ax.set_xlabel("")
    ax.legend(title="")
    savefig("01_model_metrics_vs_baseline.png")


def chart_holdout_predictions():
    path = DATA_PROCESSED / "holdout_predictions_sample.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    if not {"quantity_sold", "prediction"}.issubset(df.columns):
        return
    configure()
    sample = df.sample(min(len(df), 5000), random_state=42)

    plt.figure(figsize=(7, 6))
    plt.scatter(sample["quantity_sold"], sample["prediction"], alpha=0.25, s=12)
    max_v = max(sample["quantity_sold"].max(), sample["prediction"].max())
    plt.plot([0, max_v], [0, max_v], linestyle="--")
    plt.title("Holdout: actual demand vs predicted demand")
    plt.xlabel("Actual quantity sold")
    plt.ylabel("Predicted quantity sold")
    savefig("02_holdout_actual_vs_predicted.png")


def chart_segments():
    path = DATA_PROCESSED / "segments_kmeans.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    if "segment_name" not in df.columns:
        return
    configure()

    counts = df["segment_name"].value_counts().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(counts.index, counts.values, color="#2f6f9f")
    ax.set_title("Distributie segmente cerere")
    ax.set_xlabel("")
    ax.set_ylabel("SKU-locatii")
    ax.tick_params(axis="x", rotation=25)
    total = counts.sum()
    for bar, value in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(total * 0.01, 0.4), f"{value}\n{value / total:.0%}", ha="center", va="bottom", fontsize=8.5)
    savefig("05_kmeans_segment_distribution.png")

    if {"avg_daily_demand", "cv_demand"}.issubset(df.columns):
        plt.figure(figsize=(8, 6))
        for segment, part in df.groupby("segment_name"):
            plt.scatter(part["avg_daily_demand"], part["cv_demand"], alpha=0.7, s=35, label=segment)
        plt.title("Segmente cerere: volum vs variabilitate")
        plt.xlabel("Cerere medie zilnica")
        plt.ylabel("Coeficient variatie")
        plt.legend(fontsize=8)
        savefig("06_kmeans_demand_vs_variability.png")

    cols = ["winter_ratio", "summer_ratio", "payday_uplift", "weather_spike_uplift", "promotion_uplift", "travel_event_uplift"]
    cols = [c for c in cols if c in df.columns]
    if cols:
        profile = df.groupby("segment_name")[cols].mean().dropna(axis=1, how="all")
        if profile.empty:
            return
        fig, ax = plt.subplots(figsize=(11, 5.8))
        values = profile.values.astype(float)
        finite = values[np.isfinite(values)]
        vmax = max(1.0, float(np.nanpercentile(finite, 95)) if len(finite) else 1.0)
        cmap = plt.cm.YlGnBu.copy()
        cmap.set_bad("#f1f5f9")
        im = ax.imshow(np.ma.masked_invalid(values), aspect="auto", cmap=cmap, vmin=0, vmax=vmax)
        ax.set_title("Profil exogen pe segment")
        ax.set_xticks(range(len(profile.columns)), [short_label(c.replace("_", " "), 18) for c in profile.columns], rotation=25, ha="right")
        ax.set_yticks(range(len(profile.index)), profile.index)
        ax.grid(False)
        for y in range(profile.shape[0]):
            for x in range(profile.shape[1]):
                val = profile.iloc[y, x]
                if pd.notna(val):
                    text_color = "white" if val >= vmax * 0.6 else "#20242a"
                    ax.text(x, y, f"{val:.2f}", ha="center", va="center", fontsize=8, color=text_color)
        cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
        cbar.set_label("Medie")
        savefig("07_segment_exogenous_profile.png")


def chart_forecast_examples():
    path = DATA_PROCESSED / "forecast_30d.csv"
    if not path.exists():
        return
    df = pd.read_csv(path, parse_dates=["forecast_date"])
    sales_path = DATA_RAW / "sales_history.csv"
    sales = pd.read_csv(sales_path, parse_dates=["date"]) if sales_path.exists() else pd.DataFrame()
    pred_col = first_existing(df.columns, ["predicted_quantity", "forecast_quantity", "prediction", "yhat"])
    if pred_col is None:
        return
    configure()
    examples = [
        ("PEU-WF-WINTER-5L", "FI_HEL", "08_forecast_winter_fluid_helsinki.png"),
        ("PEU-AC-REFILL", "ES_MAD", "09_forecast_ac_refill_madrid.png"),
        ("PEU-BATT-70AH", "SE_STO", "10_forecast_battery_stockholm.png"),
    ]
    for sku, loc, fname in examples:
        part = df[(df["sku"] == sku) & (df["location_id"] == loc)].copy()
        if part.empty:
            continue
        part = part.sort_values("forecast_date")
        if "horizon_day" in part.columns:
            part = part[part["horizon_day"] <= 21].copy()
        label = part["part_name"].iloc[0] if "part_name" in part.columns else sku
        city = part["city"].iloc[0] if "city" in part.columns else loc
        hist = sales[(sales["sku"] == sku) & (sales["location_id"] == loc)].copy() if not sales.empty else pd.DataFrame()
        if not hist.empty:
            hist = (
                hist.groupby("date", as_index=False)["quantity_sold"]
                .sum()
                .sort_values("date")
            )
            hist = hist[hist["date"] >= hist["date"].max() - pd.Timedelta(days=180)].copy()
            hist["rolling_28"] = hist["quantity_sold"].rolling(28, min_periods=7).mean()

        fig, ax = plt.subplots(figsize=(11, 5.8))
        forecast_start = part["forecast_date"].min()
        forecast_end = part["forecast_date"].max()
        ax.axvspan(forecast_start, forecast_end, color="#fff3e6", alpha=0.85, zorder=0)
        ax.axvline(forecast_start, color="#667085", linestyle="--", linewidth=1.1)
        if not hist.empty:
            ax.plot(hist["date"], hist["quantity_sold"], color="#9fb6cf", alpha=0.45, linewidth=1.0, label="Vanzari zilnice")
            ax.plot(hist["date"], hist["rolling_28"], color="#2f6f9f", linewidth=2.5, label="Trend 28 zile")
        ax.plot(part["forecast_date"], part[pred_col], color="#f28e2b", marker="o", linewidth=2.4, label="Forecast 21 zile")
        forecast_total = float(part[pred_col].sum())
        baseline = float(hist["rolling_28"].dropna().tail(1).iloc[0] * len(part)) if not hist.empty and hist["rolling_28"].notna().any() else np.nan
        delta = (forecast_total - baseline) / (baseline + 1e-6) * 100 if np.isfinite(baseline) and baseline > 0 else np.nan
        summary = f"21 zile: {forecast_total:.0f} buc"
        if np.isfinite(delta):
            summary += f"\nvs trend 28z: {delta:+.0f}%"
        ax.text(
            0.98,
            0.95,
            summary,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=9,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#d0d7e2", "alpha": 0.95},
        )
        if "temperature_c" in part.columns:
            ax2 = ax.twinx()
            ax2.plot(part["forecast_date"], part["temperature_c"], color="#c0392b", linewidth=1.7, alpha=0.85, label="Temp forecast")
            ax2.axhline(0, color="#c0392b", alpha=0.25, linewidth=0.9)
            ax2.set_ylabel("Temp C", color="#c0392b")
            ax2.tick_params(axis="y", labelcolor="#c0392b")
            handles, labels = ax.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax.legend(handles + h2, labels + l2, loc="upper left", fontsize=8)
        else:
            ax.legend(loc="upper left", fontsize=8)
        ax.set_title(f"Forecast produs-locatie: {short_label(label, 44)} | {city}")
        ax.set_xlabel("")
        ax.set_ylabel("Unitati / zi")
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.tick_params(axis="x", rotation=25)
        savefig(fname)


def chart_seasonality_examples():
    path = DATA_RAW / "sales_history.csv"
    if not path.exists():
        return
    configure()
    usecols = ["date", "sku", "location_id", "quantity_sold"]
    df = pd.read_csv(path, usecols=usecols, parse_dates=["date"])
    examples = [
        ("PEU-WF-WINTER-5L", ["FI_HEL", "DE_BER", "ES_MAD"], "11_winter_fluid_monthly_by_region.png"),
        ("PEU-AC-REFILL", ["FI_HEL", "DE_BER", "ES_MAD"], "12_ac_refill_monthly_by_region.png"),
    ]
    for sku, locs, fname in examples:
        part = df[(df["sku"] == sku) & (df["location_id"].isin(locs))].copy()
        if part.empty:
            continue
        part["month"] = part["date"].dt.month
        monthly = part.groupby(["location_id", "month"], as_index=False)["quantity_sold"].mean()
        plt.figure(figsize=(10, 5))
        for loc, g in monthly.groupby("location_id"):
            plt.plot(g["month"], g["quantity_sold"], marker="o", label=loc)
        plt.title(f"Seasonality check: average monthly demand for {sku}")
        plt.xlabel("Month")
        plt.ylabel("Average daily quantity sold")
        plt.xticks(range(1, 13))
        plt.legend()
        savefig(fname)


def main():
    chart_metrics()
    chart_holdout_predictions()
    chart_segments()
    chart_forecast_examples()
    chart_seasonality_examples()
    print(f"\nCharts generated in: {OUT}")


if __name__ == "__main__":
    main()
