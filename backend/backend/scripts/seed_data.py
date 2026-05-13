from datetime import datetime
from pathlib import Path
import argparse
import csv
import os
import sqlite3
import sys

import bcrypt
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.db import DATABASE_PATH  # noqa: E402
from app.inventory.services.order_workflows import CATEGORY_SUPPLIER_MAP, seed_demo_order_workflows  # noqa: E402

GLOBAL_RAW_DATA_DIR = BASE_DIR.parent / "data" / "raw"
ENV_FILE = BASE_DIR.parent / ".env"

load_dotenv(ENV_FILE)
RAW_DATA_DIR = GLOBAL_RAW_DATA_DIR

CSV_REFRESH_TABLES = [
    "inventory_snapshot",
    "demand_history",
    "sales_history",
    "weather_daily",
    "calendar_daily",
    "calendar_events",
    "dataset_dictionary",
]


def parse_int(value, default=0):
    if value in (None, ""):
        return default
    return int(float(value))


def parse_float(value, default=0.0):
    if value in (None, ""):
        return default
    return float(value)


def parse_bool_int(value):
    if value in (None, ""):
        return 0
    return 1 if str(value).strip().lower() in ("1", "true", "yes") else 0


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def load_csv(path: Path):
    with open(path, "r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def clear_data(cursor):
    tables = [
        "audit_log",
        "order_sales_events",
        "order_client_lines",
        "order_clients",
        "order_supplier_lines",
        "order_suppliers",
        "user_stock",
        "user_location_scope",
        "users",
        "roles",
        "notifications",
        "recommendations",
        "forecast_actuals",
        "forecasts",
        "demand_history",
        "sales_history",
        "stock",
        "inventory_snapshot",
        "parts",
        "suppliers",
        "weather_daily",
        "calendar_daily",
        "calendar_events",
        "dataset_dictionary",
        "eu_locations",
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")


def clear_csv_refresh_tables(cursor):
    for table in CSV_REFRESH_TABLES:
        cursor.execute(f"DELETE FROM {table}")


def seed_users(cursor, now):
    cursor.execute(
        """
        INSERT INTO roles (role_name, description)
        VALUES (?, ?)
        ON CONFLICT(role_name) DO UPDATE SET description = excluded.description
        """,
        ("admin", "Administrator with full access"),
    )
    cursor.execute(
        """
        INSERT INTO roles (role_name, description)
        VALUES (?, ?)
        ON CONFLICT(role_name) DO UPDATE SET description = excluded.description
        """,
        ("user", "Regular user with view/edit permissions"),
    )
    cursor.execute("SELECT id FROM roles WHERE role_name = 'admin'")
    admin_role_id = cursor.fetchone()["id"]
    cursor.execute("SELECT id FROM roles WHERE role_name = 'user'")
    user_role_id = cursor.fetchone()["id"]

    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not admin_password:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD must be set before seeding the admin user.")
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (full_name, company, username, email, location_id, password_hash, role_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Admin User", "RRParts", "admin", "admin@stockoptimizer.local", None, hash_password(admin_password), admin_role_id, now, now),
    )

    demo_user_password = os.getenv("DEMO_USER_PASSWORD", "DemoPass123!")
    cursor.executemany(
        """
        INSERT OR IGNORE INTO users (full_name, company, username, email, location_id, password_hash, role_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("Paula", "RRParts", "paula", "paula@stockoptimizer.local", "FI_HEL", hash_password(demo_user_password), user_role_id, now, now),
        ],
    )


def seed_default_user_locations(cursor, now):
    user_location_defaults = [
        ("paula", "FI_HEL"),
        ("marcoboss", "ES_MAD"),
    ]

    for username, location_id in user_location_defaults:
        user_row = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if user_row is None:
            continue

        location_row = cursor.execute(
            "SELECT city FROM eu_locations WHERE location_id = ?",
            (location_id,),
        ).fetchone()
        location_name = location_row["city"] if location_row is not None else location_id

        cursor.execute(
            "UPDATE users SET location_id = ? WHERE id = ?",
            (location_id, user_row["id"]),
        )

        cursor.execute("DELETE FROM user_location_scope WHERE user_id = ?", (user_row["id"],))
        cursor.execute(
            """
            INSERT INTO user_location_scope (user_id, location_id, location, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_row["id"], location_id, location_name, now),
        )


def seed_locations(cursor):
    rows = load_csv(RAW_DATA_DIR / "eu_locations.csv")
    data = []
    for row in rows:
        winter_base = parse_float(row.get("winter_base_c"), 0.0)
        summer_base = parse_float(row.get("summer_base_c"), 0.0)
        temp_mean = (winter_base + summer_base) / 2.0
        temp_amplitude = (summer_base - winter_base) / 2.0
        data.append(
            (
                row["location_id"],
                row["city"],
                row["country"],
                row.get("country_code", ""),
                row.get("timezone"),
                parse_float(row.get("lat"), 0.0),
                parse_float(row.get("lon"), 0.0),
                row.get("climate_zone"),
                parse_float(row.get("location_demand_multiplier"), 1.0),
                temp_mean,
                temp_amplitude,
                parse_int(row.get("winter_start_month"), 0),
                parse_int(row.get("winter_end_month"), 0),
                row.get("salary_days"),
                parse_bool_int(row.get("payday_last_business_day")),
            )
        )
    cursor.executemany(
        """
        INSERT INTO eu_locations (
            location_id, city, country, country_code, timezone, latitude, longitude,
            climate_zone, demand_scale, temp_mean_c, temp_amplitude_c,
            winter_start_month, winter_end_month, salary_days, payday_last_business_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(location_id) DO UPDATE SET
            city = excluded.city,
            country = excluded.country,
            country_code = excluded.country_code,
            timezone = excluded.timezone,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            climate_zone = excluded.climate_zone,
            demand_scale = excluded.demand_scale,
            temp_mean_c = excluded.temp_mean_c,
            temp_amplitude_c = excluded.temp_amplitude_c,
            winter_start_month = excluded.winter_start_month,
            winter_end_month = excluded.winter_end_month,
            salary_days = excluded.salary_days,
            payday_last_business_day = excluded.payday_last_business_day
        """,
        data,
    )


def seed_suppliers(cursor, now):
    rows = load_csv(RAW_DATA_DIR / "suppliers.csv")
    data = []
    for row in rows:
        supplier_id = row["supplier_id"]
        reliability_score = parse_float(row.get("reliability_score"), 0.0)
        on_time_rate = reliability_score / 100.0 if reliability_score > 1.0 else reliability_score
        on_time_rate = max(0.0, min(1.0, on_time_rate))
        data.append(
            (
                supplier_id,
                supplier_id,
                row["supplier_name"],
                row.get("country_code"),
                reliability_score,
                parse_float(row.get("avg_delay_days"), 0.0),
                on_time_rate,
                parse_float(row.get("avg_delay_days"), 0.0),
                now,
            )
        )
    cursor.executemany(
        """
        INSERT INTO suppliers (
            id, supplier_code, supplier_name, country_code, reliability_score,
            avg_delay_days, avg_on_time_rate, default_lead_time_days, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            supplier_code = excluded.supplier_code,
            supplier_name = excluded.supplier_name,
            country_code = excluded.country_code,
            reliability_score = excluded.reliability_score,
            avg_delay_days = excluded.avg_delay_days,
            avg_on_time_rate = excluded.avg_on_time_rate,
            default_lead_time_days = excluded.default_lead_time_days,
            updated_at = excluded.updated_at
        """,
        data,
    )


def seed_parts(cursor):
    rows = load_csv(RAW_DATA_DIR / "parts_master.csv")
    data = []
    for row in rows:
        sku = row["sku"]
        supplier_id = row.get("supplier_id") or CATEGORY_SUPPLIER_MAP.get(row["category"])
        data.append(
            (
                sku,
                row["part_name"],
                row["category"],
                row.get("seasonality_profile"),
                parse_float(row.get("base_daily_demand", row.get("base_demand")), 0.0),
                supplier_id,
                parse_float(row.get("unit_price_eur"), 0.0),
                parse_float(row.get("salary_sensitivity"), 0.0),
                parse_int(row.get("lead_time_days"), 0),
                parse_int(row.get("min_order_qty"), 0),
                3,
            )
        )
    cursor.executemany(
        """
        INSERT INTO parts (
            sku, part_name, category, seasonality_profile, base_demand, supplier_id,
            unit_price, salary_sensitivity, lead_time_days, min_order_qty, criticality
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sku) DO UPDATE SET
            part_name = excluded.part_name,
            category = excluded.category,
            seasonality_profile = excluded.seasonality_profile,
            base_demand = excluded.base_demand,
            supplier_id = excluded.supplier_id,
            unit_price = excluded.unit_price,
            salary_sensitivity = excluded.salary_sensitivity,
            lead_time_days = excluded.lead_time_days,
            min_order_qty = excluded.min_order_qty,
            criticality = excluded.criticality
        """,
        data,
    )


def build_part_map(cursor):
    cursor.execute("SELECT id, sku FROM parts")
    return {row[1]: row[0] for row in cursor.fetchall()}


def seed_inventory(cursor, part_map):
    rows = load_csv(RAW_DATA_DIR / "inventory_snapshot.csv")
    inventory_data = []
    stock_data = []
    for row in rows:
        part_id = part_map.get(row["sku"])
        if part_id is None:
            continue
        current_stock = parse_int(row.get("current_stock") or row.get("current_stock_units"), 0)
        reorder_point = parse_int(row.get("reorder_point"), 0)
        lead_time_days = parse_int(row.get("lead_time_days"), 0)
        inventory_data.append(
            (
                row.get("snapshot_timestamp"),
                row.get("snapshot_timestamp_utc"),
                row.get("snapshot_date"),
                row.get("location_id"),
                row.get("city"),
                row.get("country_code"),
                row.get("sku"),
                row.get("part_name"),
                row.get("category"),
                row.get("supplier_id"),
                current_stock,
                reorder_point,
                parse_int(row.get("safety_stock"), 0),
                parse_int(row.get("optimal_stock"), 0),
                parse_int(row.get("min_order_qty"), 0),
                lead_time_days,
                parse_int(row.get("pending_order_qty"), 0),
                parse_int(row.get("stockout_days_history"), 0),
                parse_int(row.get("total_sales_history"), 0),
                parse_float(row.get("latent_demand_signal_history"), 0.0),
                row.get("inventory_status"),
            )
        )
        stock_data.append(
            (
                part_id,
                row.get("city") or row.get("location_id") or "UNKNOWN",
                row.get("location_id"),
                row.get("city"),
                row.get("country_code"),
                current_stock,
                reorder_point,
                parse_int(row.get("safety_stock"), 0),
                parse_int(row.get("optimal_stock"), 0),
                parse_int(row.get("min_order_qty"), 0),
                lead_time_days,
                parse_int(row.get("pending_order_qty"), 0),
                parse_int(row.get("stockout_days_history"), 0),
                parse_int(row.get("total_sales_history"), 0),
                parse_float(row.get("latent_demand_signal_history"), 0.0),
                row.get("inventory_status"),
                0.0,
                row.get("snapshot_timestamp") or row.get("snapshot_date") or datetime.now().isoformat(),
            )
        )

    cursor.executemany(
        """
        INSERT INTO inventory_snapshot (
            snapshot_timestamp, snapshot_timestamp_utc, snapshot_date, location_id, city,
            country_code, sku, part_name, category, supplier_id, current_stock,
            reorder_point, safety_stock, optimal_stock, min_order_qty, lead_time_days,
            pending_order_qty, stockout_days_history, total_sales_history,
            latent_demand_signal_history, inventory_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        inventory_data,
    )

    cursor.executemany(
        """
        INSERT INTO stock (
            part_id, location, location_id, city, country_code, current_stock,
            reorder_point, safety_stock, optimal_stock, min_order_qty, lead_time_days,
            pending_order_qty, stockout_days_history, total_sales_history,
            latent_demand_signal_history, inventory_status, avg_daily_demand_30d, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(part_id, location) DO UPDATE SET
            location_id = excluded.location_id,
            city = excluded.city,
            country_code = excluded.country_code,
            reorder_point = excluded.reorder_point,
            safety_stock = excluded.safety_stock,
            optimal_stock = excluded.optimal_stock,
            min_order_qty = excluded.min_order_qty,
            lead_time_days = excluded.lead_time_days,
            stockout_days_history = excluded.stockout_days_history,
            total_sales_history = excluded.total_sales_history,
            latent_demand_signal_history = excluded.latent_demand_signal_history,
            inventory_status = excluded.inventory_status,
            avg_daily_demand_30d = excluded.avg_daily_demand_30d,
            last_updated = excluded.last_updated
        """,
        stock_data,
    )


def seed_sales_and_demand(cursor, part_map):
    rows = load_csv(RAW_DATA_DIR / "sales_history.csv")
    sales_data = []
    demand_data = []

    for row in rows:
        part_id = part_map.get(row["sku"])
        if part_id is None:
            continue

        sales_data.append(
            (
                row.get("timestamp"),
                row.get("timestamp_utc"),
                row.get("date"),
                row.get("sku"),
                part_id,
                row.get("part_name"),
                row.get("category"),
                row.get("seasonality_profile"),
                row.get("location_id"),
                row.get("city"),
                row.get("country"),
                row.get("country_code"),
                row.get("climate_zone"),
                parse_int(row.get("quantity_sold"), 0),
                parse_float(row.get("latent_demand_signal"), 0.0),
                parse_float(row.get("unit_price_eur"), 0.0),
                parse_float(row.get("revenue_eur"), 0.0),
                parse_int(row.get("stock_on_hand_end"), 0),
                parse_bool_int(row.get("stockout_flag")),
                parse_int(row.get("day_of_week"), 0),
                row.get("day_name"),
                parse_int(row.get("day_of_month"), 0),
                parse_int(row.get("week_of_year"), 0),
                parse_int(row.get("month"), 0),
                parse_int(row.get("quarter"), 0),
                parse_int(row.get("year"), 0),
                row.get("season"),
                parse_bool_int(row.get("is_weekend")),
                parse_float(row.get("temperature_c"), 0.0),
                parse_float(row.get("temp_change_1d_c"), 0.0),
                parse_float(row.get("temp_change_3d_c"), 0.0),
                parse_float(row.get("abs_temp_change_3d_c"), 0.0),
                parse_float(row.get("rain_mm"), 0.0),
                parse_float(row.get("snow_cm"), 0.0),
                parse_bool_int(row.get("cold_snap_flag")),
                parse_bool_int(row.get("heatwave_flag")),
                parse_bool_int(row.get("weather_spike_flag")),
                parse_bool_int(row.get("temperature_drop_flag")),
                parse_bool_int(row.get("temperature_rise_flag")),
                parse_bool_int(row.get("is_payday")),
                parse_bool_int(row.get("is_payday_window")),
                parse_bool_int(row.get("is_holiday")),
                parse_bool_int(row.get("is_school_holiday")),
                row.get("event_name"),
                row.get("event_type"),
                row.get("affected_categories"),
                parse_float(row.get("event_multiplier"), 0.0),
                parse_bool_int(row.get("promotion_flag")),
                parse_bool_int(row.get("service_campaign_flag")),
                parse_float(row.get("fuel_price_eur_l"), 0.0),
                parse_float(row.get("mobility_index"), 0.0),
                parse_float(row.get("mean_demand_before_stock"), 0.0),
                parse_float(row.get("weather_spike_applied"), 0.0),
                parse_float(row.get("salary_spike_applied"), 0.0),
                parse_float(row.get("calendar_spike_applied"), 0.0),
            )
        )

        demand_data.append(
            (
                part_id,
                row.get("date"),
                row.get("location_id") or row.get("city") or "UNKNOWN",
                "location",
                parse_int(row.get("quantity_sold"), 0),
            )
        )

    cursor.executemany(
        """
        INSERT INTO sales_history (
            timestamp, timestamp_utc, date, sku, part_id, part_name, category,
            seasonality_profile, location_id, city, country, country_code, climate_zone,
            quantity_sold, latent_demand_signal, unit_price_eur, revenue_eur,
            stock_on_hand_end, stockout_flag, day_of_week, day_name, day_of_month,
            week_of_year, month, quarter, year, season, is_weekend, temperature_c,
            temp_change_1d_c, temp_change_3d_c, abs_temp_change_3d_c, rain_mm, snow_cm,
            cold_snap_flag, heatwave_flag, weather_spike_flag, temperature_drop_flag,
            temperature_rise_flag, is_payday, is_payday_window, is_holiday,
            is_school_holiday, event_name, event_type, affected_categories,
            event_multiplier, promotion_flag, service_campaign_flag, fuel_price_eur_l,
            mobility_index, mean_demand_before_stock, weather_spike_applied,
            salary_spike_applied, calendar_spike_applied
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sales_data,
    )

    cursor.executemany(
        """
        INSERT INTO demand_history (
            part_id, sale_date, location, location_type, sales_quantity
        ) VALUES (?, ?, ?, ?, ?)
        """,
        demand_data,
    )


def seed_weather(cursor):
    rows = load_csv(RAW_DATA_DIR / "weather_daily.csv")
    data = []
    for row in rows:
        data.append(
            (
                row.get("timestamp"),
                row.get("timestamp_utc"),
                row.get("date"),
                row.get("location_id"),
                row.get("city"),
                row.get("country_code"),
                row.get("climate_zone"),
                parse_float(row.get("temperature_c"), 0.0),
                parse_float(row.get("temp_change_1d_c"), 0.0),
                parse_float(row.get("temp_change_3d_c"), 0.0),
                parse_float(row.get("abs_temp_change_3d_c"), 0.0),
                parse_float(row.get("rain_mm"), 0.0),
                parse_float(row.get("snow_cm"), 0.0),
                parse_bool_int(row.get("cold_snap_flag")),
                parse_bool_int(row.get("heatwave_flag")),
                parse_bool_int(row.get("weather_spike_flag")),
                parse_bool_int(row.get("temperature_drop_flag")),
                parse_bool_int(row.get("temperature_rise_flag")),
            )
        )
    cursor.executemany(
        """
        INSERT INTO weather_daily (
            timestamp, timestamp_utc, date, location_id, city, country_code,
            climate_zone, temperature_c, temp_change_1d_c, temp_change_3d_c,
            abs_temp_change_3d_c, rain_mm, snow_cm, cold_snap_flag, heatwave_flag,
            weather_spike_flag, temperature_drop_flag, temperature_rise_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        data,
    )


def seed_calendar_table(cursor, filename, table_name):
    rows = load_csv(RAW_DATA_DIR / filename)
    data = []
    for row in rows:
        data.append(
            (
                row.get("timestamp"),
                row.get("timestamp_utc"),
                row.get("date"),
                row.get("location_id"),
                row.get("city"),
                row.get("country_code"),
                parse_bool_int(row.get("is_payday")),
                parse_bool_int(row.get("is_payday_window")),
                parse_bool_int(row.get("is_holiday")),
                parse_bool_int(row.get("is_school_holiday")),
                row.get("event_name"),
                row.get("event_type"),
                row.get("affected_categories"),
                parse_float(row.get("event_multiplier"), 0.0),
                parse_bool_int(row.get("promotion_flag")),
                parse_bool_int(row.get("service_campaign_flag")),
            )
        )
    cursor.executemany(
        f"""
        INSERT INTO {table_name} (
            timestamp, timestamp_utc, date, location_id, city, country_code,
            is_payday, is_payday_window, is_holiday, is_school_holiday,
            event_name, event_type, affected_categories, event_multiplier,
            promotion_flag, service_campaign_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        data,
    )


def seed_dictionary(cursor):
    rows = load_csv(RAW_DATA_DIR / "dataset_dictionary.csv")
    data = [(row.get("file"), row.get("column"), row.get("description")) for row in rows]
    cursor.executemany(
        "INSERT INTO dataset_dictionary (file, column_name, description) VALUES (?, ?, ?)",
        data,
    )


def main(reset: bool = False):
    if not DATABASE_PATH.exists():
        print(f"Database file not found: {DATABASE_PATH}")
        print("Run scripts/init_db.py first.")
        return

    if not RAW_DATA_DIR.exists():
        print(f"ML raw data folder not found: {RAW_DATA_DIR}")
        print("Ensure project-level CSV copy exists at data/raw.")
        return

    now = datetime.now().isoformat(timespec="seconds")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    try:
        if reset:
            clear_data(cursor)
        else:
            clear_csv_refresh_tables(cursor)
        seed_users(cursor, now)
        seed_locations(cursor)
        seed_default_user_locations(cursor, now)
        seed_suppliers(cursor, now)
        seed_parts(cursor)
        part_map = build_part_map(cursor)
        seed_inventory(cursor, part_map)
        seed_sales_and_demand(cursor, part_map)
        seed_weather(cursor)
        seed_calendar_table(cursor, "calendar_daily.csv", "calendar_daily")
        seed_calendar_table(cursor, "calendar_events.csv", "calendar_events")
        seed_dictionary(cursor)
        seed_demo_order_workflows(connection)

        connection.commit()
        mode = "reset seed" if reset else "safe refresh"
        print(f"Seed completed from data/raw CSV files ({mode}).")
        print(f"Source folder: {RAW_DATA_DIR}")
    except Exception as error:
        connection.rollback()
        print(f"Seed failed: {error}")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed or refresh the Stock Optimizer SQLite database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all seeded/runtime tables before loading CSV data. Omit for a non-destructive refresh.",
    )
    args = parser.parse_args()
    main(reset=args.reset)
