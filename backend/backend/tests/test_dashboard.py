import sqlite3

import app.analytics.routers.dashboard as dashboard_router
from app.core.auth import require_authenticated_user
from app.main import app


def test_sales_flow_allows_explicit_other_location_for_user(client):
    import app.db as db_module

    connection = sqlite3.connect(db_module.DATABASE_PATH)
    cursor = connection.cursor()
    cursor.executemany(
        """
        INSERT INTO sales_history (date, sku, category, location_id, city, quantity_sold)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-01-10", "PART-001", "Brakes", "RO_BUC", "Bucharest", 10),
            ("2026-02-10", "PART-001", "Brakes", "RO_BUC", "Bucharest", 12),
            ("2026-01-10", "PART-001", "Brakes", "FR_PAR", "Paris", 80),
            ("2026-02-10", "PART-001", "Brakes", "FR_PAR", "Paris", 90),
        ],
    )
    connection.commit()
    connection.close()

    app.dependency_overrides[require_authenticated_user] = lambda: {
        "id": 2,
        "role_name": "user",
        "user_location_ids": ["RO_BUC"],
        "user_locations": ["Bucharest"],
    }

    default_response = client.get("/dashboard/sales-flow?months=2")
    assert default_response.status_code == 200
    default_series = default_response.json()["series"]
    assert default_series
    assert default_series[0]["values"] == [10, 12]

    override_response = client.get("/dashboard/sales-flow?months=2&location=FR_PAR")
    assert override_response.status_code == 200
    override_series = override_response.json()["series"]
    assert override_series
    assert override_series[0]["values"] == [80, 90]


def test_dashboard_ml_forecast_uses_user_default_location(client, monkeypatch):
    app.dependency_overrides[require_authenticated_user] = lambda: {
        "id": 2,
        "role_name": "user",
        "location_id": "FI_HEL",
        "user_location_ids": ["FI_HEL"],
        "user_locations": ["Helsinki"],
    }

    def fake_safe_ml_service_get(path, params=None):
        assert path == "/forecast"
        assert params["location_id"] == "FI_HEL"
        return ([{"sku": "PART-001", "location_id": "FI_HEL", "predicted_quantity": 12.5}], None)

    monkeypatch.setattr(dashboard_router, "safe_ml_service_get", fake_safe_ml_service_get)

    response = client.get("/dashboard/ml/forecast")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["location_id"] == "FI_HEL"
    assert body["items"][0]["location_id"] == "FI_HEL"


def test_dashboard_ml_recommendations_falls_back_safely_when_unavailable(client, monkeypatch):
    app.dependency_overrides[require_authenticated_user] = lambda: {
        "id": 2,
        "role_name": "user",
        "location_id": "ES_MAD",
        "user_location_ids": ["ES_MAD"],
        "user_locations": ["Madrid"],
    }

    def fake_safe_ml_service_get(path, params=None):
        assert path == "/recommendations"
        return ([], "connection failed")

    monkeypatch.setattr(dashboard_router, "safe_ml_service_get", fake_safe_ml_service_get)

    response = client.get("/dashboard/ml/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["location_id"] == "ES_MAD"
    assert body["items"] == []
    assert body["error"] == "connection failed"
