from datetime import date
from pathlib import Path
import sqlite3

import bcrypt
import pytest
from fastapi.testclient import TestClient

from app.core.auth import require_admin, require_authenticated_user
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_stock_optimizer.db"
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")

    with open(schema_path, "r", encoding="utf-8") as schema_file:
        connection.executescript(schema_file.read())

    now = date.today().isoformat()
    admin_hash = bcrypt.hashpw("AdminPass123!".encode(), bcrypt.gensalt()).decode()

    cursor = connection.cursor()
    cursor.execute("INSERT INTO roles (role_name, description) VALUES (?, ?)", ("admin", "Admin role"))
    admin_role_id = cursor.lastrowid
    cursor.execute("INSERT INTO roles (role_name, description) VALUES (?, ?)", ("user", "User role"))
    user_role_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO users (full_name, company, username, email, password_hash, role_id, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Admin User", "RRParts", "admin", "admin@test.local", admin_hash, admin_role_id, 1, now, now),
    )
    
    cursor.execute(
        """
        INSERT INTO users (full_name, company, username, email, password_hash, role_id, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Test User", "Test Inc", "testuser", "testuser@test.local", admin_hash, user_role_id, 1, now, now),
    )

    cursor.executemany(
        """
        INSERT INTO eu_locations (
            location_id, city, country, country_code, timezone, latitude, longitude, climate_zone,
            demand_scale, temp_mean_c, temp_amplitude_c, winter_start_month, winter_end_month,
            salary_days, payday_last_business_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("RO_BUC", "Bucharest", "Romania", "RO", "Europe/Bucharest", 44.4268, 26.1025, "temperate", 1.0, 10.0, 12.0, 11, 3, "25", 0),
            ("FR_PAR", "Paris", "France", "FR", "Europe/Paris", 48.8566, 2.3522, "temperate", 1.0, 12.0, 9.0, 11, 3, "25", 1),
        ],
    )

    cursor.execute(
        """
        INSERT INTO suppliers (id, supplier_code, supplier_name, country_code, reliability_score, avg_delay_days, avg_on_time_rate, default_lead_time_days, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("SUP-TEST", "SUP-TEST", "Test Supplier", "RO", 90.0, 2.0, 0.9, 5, now),
    )
    supplier_id = "SUP-TEST"

    cursor.execute(
        """
        INSERT INTO parts (sku, part_name, category, supplier_id, unit_price, lead_time_days, criticality)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("PART-001", "Test Part", "Brakes", supplier_id, 100.0, 7, 3),
    )
    connection.commit()
    connection.close()

    import app.db as db_module
    from app.core.auth import get_current_user

    monkeypatch.setattr(db_module, "DATABASE_PATH", db_path)
    
    # Mock admin user for testing (default)
    mock_admin_user = {
        "id": 1,
        "username": "admin",
        "email": "admin@test.local",
        "full_name": "Admin User",
        "company": "RRParts",
        "is_active": True,
        "role_name": "admin",
        "role": "admin",
        "user_locations": ["WH-A", "WH-B", "WH-C"],
        "user_location_ids": [],
    }
    
    app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    app.dependency_overrides[require_admin] = lambda: mock_admin_user
    app.dependency_overrides[require_authenticated_user] = lambda: mock_admin_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
