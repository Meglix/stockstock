from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


def _series(frame: pd.DataFrame, column: str, default=0):
    if column in frame.columns:
        return frame[column]
    return pd.Series(default, index=frame.index)


def _supplier_for_category(category: str, default_supplier: str) -> str:
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


def generate_recommendations(
    raw_dir: str | Path = "data/raw",
    processed_dir: str | Path = "data/processed",
    horizon: int = 30,
) -> Dict[str, pd.DataFrame]:
    raw_path = Path(raw_dir)
    processed_path = Path(processed_dir)
    forecast_file = processed_path / f"forecast_{horizon}d.csv"
    if not forecast_file.exists():
        raise FileNotFoundError(f"Lipseste {forecast_file}. Ruleaza mai intai forecast.py")

    forecast = pd.read_csv(forecast_file)
    inventory = pd.read_csv(raw_path / "inventory_snapshot.csv")
    parts = pd.read_csv(raw_path / "parts_master.csv")
    suppliers = pd.read_csv(raw_path / "suppliers.csv").rename(columns={"country_code": "supplier_country_code"})
    segments_path = processed_path / "segments_kmeans.csv"
    segments = pd.read_csv(segments_path) if segments_path.exists() else pd.DataFrame()
    default_supplier = str(suppliers["supplier_id"].iloc[0]) if "supplier_id" in suppliers.columns and not suppliers.empty else "UNKNOWN"

    part_cols = [col for col in ["sku", "lead_time_days", "safety_stock_units", "min_order_qty", "supplier_id"] if col in parts.columns]
    if part_cols != ["sku"]:
        inventory = inventory.merge(parts[part_cols], on="sku", how="left", suffixes=("", "_part"))
    inventory["current_stock"] = pd.to_numeric(_series(inventory, "current_stock", _series(inventory, "current_stock_units", 0)), errors="coerce").fillna(0)
    inventory["safety_stock"] = pd.to_numeric(_series(inventory, "safety_stock", _series(inventory, "safety_stock_units", _series(inventory, "reorder_point", 0))), errors="coerce").fillna(0)
    if "lead_time_days_part" in inventory.columns:
        inventory["lead_time_days"] = pd.to_numeric(_series(inventory, "lead_time_days"), errors="coerce").fillna(pd.to_numeric(inventory["lead_time_days_part"], errors="coerce"))
    inventory["lead_time_days"] = pd.to_numeric(_series(inventory, "lead_time_days", 7), errors="coerce").fillna(7)
    inventory["min_order_qty"] = pd.to_numeric(_series(inventory, "min_order_qty", _series(inventory, "reorder_point", inventory["safety_stock"])), errors="coerce").fillna(1).clip(lower=1)
    inventory["optimal_stock"] = pd.to_numeric(
        _series(inventory, "optimal_stock", _series(inventory, "reorder_point", 0) + inventory["safety_stock"]),
        errors="coerce",
    ).fillna(inventory["safety_stock"])

    agg = forecast.groupby(["sku", "location_id"], as_index=False).agg(
        part_name=("part_name", "first"),
        category=("category", "first"),
        city=("city", "first"),
        country_code=("country_code", "first"),
        climate_zone=("climate_zone", "first"),
        demand_7d=("predicted_quantity", lambda x: x.head(7).sum()),
        demand_14d=("predicted_quantity", lambda x: x.head(14).sum()),
        demand_horizon=("predicted_quantity", "sum"),
        max_daily_forecast=("predicted_quantity", "max"),
        avg_daily_forecast=("predicted_quantity", "mean"),
        weather_spike_days=("weather_spike_flag", "sum"),
        cold_snap_days=("cold_snap_flag", "sum"),
        heatwave_days=("heatwave_flag", "sum"),
        payday_window_days=("is_payday_window", "sum"),
    )
    merged = agg.merge(inventory, on=["sku", "location_id"], suffixes=("", "_inventory"), how="left")
    if "supplier_id" not in merged.columns:
        merged["supplier_id"] = merged["category"].map(lambda category: _supplier_for_category(category, default_supplier))
    merged["supplier_id"] = merged["supplier_id"].fillna(merged["category"].map(lambda category: _supplier_for_category(category, default_supplier)))
    merged = merged.merge(suppliers, on="supplier_id", how="left")
    if not segments.empty:
        merged = merged.merge(segments[["sku", "location_id", "segment_name", "cluster"]], on=["sku", "location_id"], how="left")
    else:
        merged["segment_name"] = "unknown"
        merged["cluster"] = -1

    rec_rows: List[Dict[str, object]] = []
    for _, row in merged.iterrows():
        avg_daily = max(float(row["avg_daily_forecast"]), 0.01)
        lead = int(row["lead_time_days"])
        current_stock = float(row["current_stock"])
        safety_stock = float(row["safety_stock"])
        min_order_qty = int(row["min_order_qty"])
        lead_time_demand = avg_daily * lead
        reorder_need = lead_time_demand + safety_stock - current_stock
        days_until_stockout = current_stock / avg_daily
        coverage_ratio = current_stock / max(1.0, float(row["demand_horizon"]))
        action = "monitor"
        priority = "low"
        recommended_qty = 0
        reason = "Stocul acopera forecast-ul pe orizontul analizat."
        if reorder_need > 0 or days_until_stockout <= lead + 2:
            action = "order"
            priority = "high" if days_until_stockout <= lead else "medium"
            recommended_qty = int(max(min_order_qty, np.ceil(reorder_need + avg_daily * 7)))
            reason = f"Risc stockout: {days_until_stockout:.1f} zile acoperire vs lead time {lead} zile."
        elif coverage_ratio > 2.2 and current_stock > float(row["optimal_stock"]) * 1.25:
            action = "reduce"
            priority = "medium"
            recommended_qty = int(max(0, np.floor(current_stock - float(row["optimal_stock"]))))
            reason = f"Stoc peste optim: acoperire {coverage_ratio:.1f}x fata de cererea estimata pe {horizon} zile."
        if row.get("segment_name") == "slow_moving_intermittent" and action == "order":
            recommended_qty = int(max(min_order_qty, min(recommended_qty, float(row["optimal_stock"]))))
            reason += " Segment slow-moving: comanda este plafonata pentru a evita overstock."
        if int(row["weather_spike_days"]) > 0 and row["category"] in ["winter_fluids", "battery", "wipers", "coolant", "ac_cooling"]:
            reason += " Forecast-ul include spike meteo in orizont."
        if int(row["payday_window_days"]) > 0 and row["category"] in ["maintenance", "brakes", "tires", "battery"]:
            reason += " Include fereastra de salariu, unde istoricul are uplift de cerere."
        rec_rows.append(
            {
                "sku": row["sku"],
                "part_name": row["part_name"],
                "category": row["category"],
                "location_id": row["location_id"],
                "city": row["city"],
                "country_code": row["country_code"],
                "climate_zone": row["climate_zone"],
                "segment_name": row.get("segment_name", "unknown"),
                "current_stock": int(current_stock),
                "safety_stock": int(safety_stock),
                "optimal_stock": int(row["optimal_stock"]),
                "lead_time_days": lead,
                "supplier_id": row["supplier_id"],
                "supplier_name": row.get("supplier_name", ""),
                "supplier_reliability_score": row.get("reliability_score", np.nan),
                "forecast_demand_7d": round(float(row["demand_7d"]), 2),
                "forecast_demand_14d": round(float(row["demand_14d"]), 2),
                f"forecast_demand_{horizon}d": round(float(row["demand_horizon"]), 2),
                "avg_daily_forecast": round(avg_daily, 3),
                "max_daily_forecast": round(float(row["max_daily_forecast"]), 3),
                "days_until_stockout": round(days_until_stockout, 2),
                "coverage_ratio_horizon": round(coverage_ratio, 3),
                "weather_spike_days_in_horizon": int(row["weather_spike_days"]),
                "cold_snap_days_in_horizon": int(row["cold_snap_days"]),
                "heatwave_days_in_horizon": int(row["heatwave_days"]),
                "payday_window_days_in_horizon": int(row["payday_window_days"]),
                "recommended_action": action,
                "recommended_qty": recommended_qty,
                "priority": priority,
                "explanation": reason,
            }
        )
    recommendations = pd.DataFrame(rec_rows).sort_values(["priority", "recommended_action", "days_until_stockout"], ascending=[True, True, True])

    surplus = recommendations[recommendations["recommended_action"] == "reduce"]
    risky = recommendations[recommendations["recommended_action"] == "order"]
    transfer_rows: List[Dict[str, object]] = []
    for _, risk in risky.iterrows():
        donors = surplus[(surplus["sku"] == risk["sku"]) & (surplus["location_id"] != risk["location_id"])]
        if not donors.empty:
            donor = donors.sort_values("recommended_qty", ascending=False).iloc[0]
            qty = int(min(risk["recommended_qty"], donor["recommended_qty"]))
            if qty > 0:
                transfer_rows.append(
                    {
                        "sku": risk["sku"],
                        "part_name": risk["part_name"],
                        "from_location_id": donor["location_id"],
                        "from_city": donor["city"],
                        "to_location_id": risk["location_id"],
                        "to_city": risk["city"],
                        "transfer_qty": qty,
                        "reason": "Transfer sugerat: locatia destinatie are risc de stockout, iar locatia sursa are surplus.",
                    }
                )
    transfers = pd.DataFrame(transfer_rows)

    alerts: List[Dict[str, object]] = []
    for _, rec in recommendations.iterrows():
        if rec["recommended_action"] == "order" and rec["priority"] in ("high", "medium"):
            alerts.append(
                {
                    "alert_type": "stockout_risk",
                    "priority": rec["priority"],
                    "sku": rec["sku"],
                    "location_id": rec["location_id"],
                    "city": rec["city"],
                    "message": f"{rec['part_name']} are acoperire estimata de {rec['days_until_stockout']} zile; recomandare order {rec['recommended_qty']} buc.",
                }
            )
        if rec["recommended_action"] == "reduce":
            alerts.append(
                {
                    "alert_type": "overstock",
                    "priority": rec["priority"],
                    "sku": rec["sku"],
                    "location_id": rec["location_id"],
                    "city": rec["city"],
                    "message": f"{rec['part_name']} are surplus estimat; reduce/transfer {rec['recommended_qty']} buc.",
                }
            )
        if rec["weather_spike_days_in_horizon"] > 0 and rec["category"] in ["winter_fluids", "battery", "wipers", "ac_cooling", "coolant"]:
            alerts.append(
                {
                    "alert_type": "weather_demand_spike",
                    "priority": "medium",
                    "sku": rec["sku"],
                    "location_id": rec["location_id"],
                    "city": rec["city"],
                    "message": f"Spike meteo in forecast pentru {rec['part_name']}; verifica stocul si furnizorul.",
                }
            )
    alerts_df = pd.DataFrame(alerts)
    recommendations.to_csv(processed_path / "recommendations.csv", index=False)
    alerts_df.to_csv(processed_path / "alerts.csv", index=False)
    if not transfers.empty:
        transfers.to_csv(processed_path / "transfer_suggestions.csv", index=False)
    else:
        pd.DataFrame(columns=["sku", "from_location_id", "to_location_id", "transfer_qty", "reason"]).to_csv(processed_path / "transfer_suggestions.csv", index=False)
    return {"recommendations": recommendations, "alerts": alerts_df, "transfers": transfers}


if __name__ == "__main__":
    output = generate_recommendations()
    print({key: int(value.shape[0]) for key, value in output.items()})
