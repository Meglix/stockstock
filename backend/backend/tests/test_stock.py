from app.core.auth import require_authenticated_user
from app.main import app


def test_create_list_get_and_update_stock(client):
    create_payload = {
        "part_id": 1,
        "location": "WH-A",
        "location_id": "LOC-WH-A",
        "city": "Bucharest",
        "country_code": "RO",
        "current_stock": 10,
        "reorder_point": 12,
        "safety_stock": 5,
        "optimal_stock": 20,
        "min_order_qty": 2,
        "lead_time_days": 4,
        "pending_order_qty": 0,
        "stockout_days_history": 1,
        "total_sales_history": 50,
        "latent_demand_signal_history": 0,
        "inventory_status": "low",
        "avg_daily_demand_30d": 1,
    }

    create_response = client.post("/stock", json=create_payload)
    assert create_response.status_code == 200
    assert create_response.json()["message"] == "Stock record created"

    list_response = client.get("/stock")
    assert list_response.status_code == 200
    stock_rows = list_response.json()
    assert len(stock_rows) >= 1
    assert stock_rows[0]["part_id"] == 1

    get_response = client.get("/stock/1")
    assert get_response.status_code == 200
    by_part = get_response.json()
    assert len(by_part) >= 1
    assert by_part[0]["location"] == "WH-A"

    update_response = client.patch(
        "/stock/1/WH-A",
        json={
            "current_stock": 15,
            "inventory_status": "ok",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["message"] == "Stock updated"


def test_user_stock_scope_uses_location_id(client):
    for location, location_id in [("Bucharest", "RO_BUC"), ("Paris", "FR_PAR")]:
        response = client.post(
            "/stock",
            json={
                "part_id": 1,
                "location": location,
                "location_id": location_id,
                "city": location,
                "country_code": location_id[:2],
                "current_stock": 10,
                "reorder_point": 5,
                "safety_stock": 3,
                "optimal_stock": 20,
                "avg_daily_demand_30d": 1,
            },
        )
        assert response.status_code == 200

    app.dependency_overrides[require_authenticated_user] = lambda: {
        "id": 2,
        "role_name": "user",
        "user_location_ids": ["RO_BUC"],
        "user_locations": ["Bucharest"],
    }

    response = client.get("/stock")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["location_id"] == "RO_BUC"

    detail_response = client.get("/stock/1")

    assert detail_response.status_code == 200
    detail_rows = detail_response.json()
    assert len(detail_rows) == 1
    assert detail_rows[0]["location_id"] == "RO_BUC"


def test_create_stock_rejects_invalid_policy(client):
    payload = {
        "part_id": 1,
        "location": "WH-B",
        "current_stock": 2,
        "reorder_point": 3,
        "safety_stock": 5,
        "optimal_stock": 4,
        "avg_daily_demand_30d": 0,
    }

    response = client.post("/stock", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("optimal_stock must be greater than or equal to safety_stock" in item["msg"] for item in detail)
