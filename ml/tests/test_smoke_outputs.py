from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DECISION_DIR = PROCESSED_DIR / "decision_layer"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class MlOutputSmokeTests(unittest.TestCase):
    def test_dataset_summary_matches_current_demo_scope(self) -> None:
        summary = read_json(RAW_DIR / "dataset_summary.json")

        self.assertEqual(summary["rows"], 157896)
        self.assertEqual(summary["locations"], 12)
        self.assertEqual(summary["skus"], 18)
        self.assertEqual(summary["date_min"], "2024-01-01")
        self.assertEqual(summary["date_max"], "2025-12-31")

    def test_forecast_output_contract(self) -> None:
        path = PROCESSED_DIR / "forecast_30d.csv"
        required_columns = {
            "forecast_date",
            "horizon_day",
            "sku",
            "part_name",
            "location_id",
            "city",
            "predicted_quantity",
            "predicted_revenue_eur",
            "temperature_c",
            "cold_snap_flag",
            "heatwave_flag",
            "segment_name",
        }

        columns = set(pd.read_csv(path, nrows=0).columns)
        self.assertTrue(required_columns.issubset(columns))

        forecast = pd.read_csv(path, usecols=list(required_columns))
        self.assertEqual(len(forecast), 6480)
        self.assertEqual(forecast["sku"].nunique(), 18)
        self.assertEqual(forecast["location_id"].nunique(), 12)
        self.assertEqual(int(forecast["horizon_day"].min()), 1)
        self.assertEqual(int(forecast["horizon_day"].max()), 30)
        self.assertTrue((forecast["predicted_quantity"] >= 0).all())
        self.assertTrue((forecast["predicted_revenue_eur"] >= 0).all())

    def test_optional_open_meteo_output_contract(self) -> None:
        path = RAW_DIR / "weather_forecast_open_meteo.csv"
        if not path.exists():
            self.skipTest("Open-Meteo forecast file has not been fetched yet.")

        required_columns = {
            "date",
            "location_id",
            "temperature_c",
            "rain_mm",
            "snow_cm",
            "temp_change_1d_c",
            "temp_change_3d_c",
            "abs_temp_change_3d_c",
            "cold_snap_flag",
            "heatwave_flag",
            "weather_spike_flag",
            "temperature_drop_flag",
            "temperature_rise_flag",
            "weather_source",
        }
        weather = pd.read_csv(path)
        self.assertTrue(required_columns.issubset(set(weather.columns)))
        self.assertEqual(weather["location_id"].nunique(), 12)
        self.assertTrue(set(weather["weather_source"]).issubset({"open_meteo_forecast"}))
        self.assertTrue((weather["rain_mm"] >= 0).all())
        self.assertTrue((weather["snow_cm"] >= 0).all())

    def test_recommendations_output_contract(self) -> None:
        path = PROCESSED_DIR / "recommendations.csv"
        required_columns = {
            "sku",
            "location_id",
            "current_stock",
            "safety_stock",
            "optimal_stock",
            "lead_time_days",
            "supplier_id",
            "supplier_name",
            "forecast_demand_7d",
            "forecast_demand_14d",
            "forecast_demand_30d",
            "days_until_stockout",
            "recommended_action",
            "recommended_qty",
            "priority",
            "explanation",
        }

        columns = set(pd.read_csv(path, nrows=0).columns)
        self.assertTrue(required_columns.issubset(columns))

        recommendations = pd.read_csv(path, usecols=list(required_columns))
        self.assertEqual(len(recommendations), 216)
        self.assertTrue(set(recommendations["recommended_action"]).issubset({"order", "reduce", "monitor"}))
        self.assertTrue({"order", "reduce", "monitor"}.issubset(set(recommendations["recommended_action"])))
        self.assertTrue(set(recommendations["priority"]).issubset({"high", "medium", "low"}))
        self.assertTrue((recommendations["recommended_qty"] >= 0).all())
        self.assertTrue((recommendations["current_stock"] >= 0).all())

    def test_model_metrics_are_consistent_with_documentation(self) -> None:
        metrics = read_json(PROCESSED_DIR / "model_metrics.json")
        forecast_metrics = metrics["forecast_model_metrics"]
        baseline_metrics = metrics["baseline_rolling_mean_28_metrics"]

        self.assertLess(forecast_metrics["WAPE_percent"], baseline_metrics["WAPE_percent"])
        self.assertLess(forecast_metrics["MAE"], baseline_metrics["MAE"])
        self.assertGreater(forecast_metrics["R2"], 0.9)
        self.assertEqual(metrics["validation_start_date"], "2025-11-17")
        self.assertEqual(metrics["validation_end_date"], "2025-12-31")

    def test_alert_backtest_is_explicitly_a_proxy(self) -> None:
        backtest = read_json(PROCESSED_DIR / "business_alert_backtest_21d.json")

        self.assertEqual(backtest["evaluation_type"], "risk_ranking_proxy")
        self.assertIn("not exact sales", backtest["primary_use"])
        self.assertIn("ranking/risc", backtest["note"])
        self.assertEqual(
            backtest["positive_event_windows"],
            backtest["true_positive_alerts"] + backtest["false_negative_alerts"],
        )

    def test_decision_layer_outputs_exist(self) -> None:
        manifest = read_json(DECISION_DIR / "decision_layer_manifest.json")

        self.assertEqual(manifest["horizon_days"], 21)
        self.assertEqual(manifest["row_counts"]["stock_risk_rows"], 216)
        self.assertEqual(manifest["row_counts"]["sensitivity_profiles"], 216)
        self.assertEqual(manifest["row_counts"]["risk_map_locations"], 12)

        stock_risk_columns = set(pd.read_csv(DECISION_DIR / "stock_risk_reorder_engine.csv", nrows=0).columns)
        self.assertTrue(
            {
                "sku",
                "location_id",
                "forecast_21d_units",
                "coverage_days",
                "recommended_order_qty",
                "risk_status",
                "reorder_message",
            }.issubset(stock_risk_columns)
        )


class ApiSmokeTests(unittest.TestCase):
    def test_fastapi_handlers_return_demo_data(self) -> None:
        from app import main

        health = main.health()
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["files"]["forecast_30d"])
        self.assertTrue(health["files"]["decision_layer"])

        forecast_rows = main.forecast_for_sku("PEU-WF-WINTER-5L", location_id="FI_HEL", horizon=30, limit=3)
        self.assertEqual(len(forecast_rows), 3)
        self.assertEqual({row["sku"] for row in forecast_rows}, {"PEU-WF-WINTER-5L"})
        self.assertEqual({row["location_id"] for row in forecast_rows}, {"FI_HEL"})

        order_rows = main.recommendations(action="order", priority="high", limit=5)
        self.assertGreater(len(order_rows), 0)
        self.assertTrue(all(row["recommended_action"] == "order" for row in order_rows))
        self.assertTrue(all(row["priority"] == "high" for row in order_rows))

        kpis = main.kpis()
        self.assertEqual(kpis["total_skus"], 18)
        self.assertEqual(kpis["total_locations"], 12)
        self.assertEqual(kpis["forecast_rows"], 6480)

        if (RAW_DIR / "weather_forecast_open_meteo.csv").exists():
            live_weather = main.open_meteo_weather(limit=3)
            self.assertGreater(len(live_weather), 0)
            self.assertTrue(all(row["weather_source"] == "open_meteo_forecast" for row in live_weather))

        dashboard = main.dashboard_location(
            location_id="FI_HEL",
            sku="PEU-WF-WINTER-5L",
            horizon=16,
            limit=3,
        )
        self.assertEqual(dashboard["dashboard"], "stock_risk_dashboard")
        self.assertIn("location_risk_overview", dashboard["sections"])
        self.assertIn("forecast_weather", dashboard["sections"])
        self.assertIn("alerts_recommended_orders", dashboard["sections"])
        self.assertGreater(len(dashboard["sections"]["forecast_weather"]["forecast"]), 0)
        self.assertGreater(len(dashboard["sections"]["alerts_recommended_orders"]["recommended_orders"]), 0)


if __name__ == "__main__":
    unittest.main()
