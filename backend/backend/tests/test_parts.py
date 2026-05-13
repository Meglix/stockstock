def test_get_parts_returns_seeded_part(client):
    response = client.get("/parts")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["sku"] == "PART-001"
    assert data[0]["supplier_id"] == "SUP-TEST"


def test_create_update_delete_part(client):
    create_payload = {
        "sku": "PART-NEW-01",
        "part_name": "New Test Part",
        "category": "Engine",
        "seasonality_profile": "all-year",
        "base_demand": 5,
        "supplier_id": "SUP-TEST",
        "unit_price": 120.0,
        "salary_sensitivity": 0.2,
        "lead_time_days": 4,
        "min_order_qty": 2,
        "criticality": 4,
    }

    create_response = client.post("/parts", json=create_payload)
    assert create_response.status_code == 200
    part_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/parts/{part_id}",
        json={"unit_price": 140.0, "criticality": 5},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["message"] == "Part updated"

    get_response = client.get(f"/parts/{part_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["unit_price"] == 140.0
    assert body["criticality"] == 5

    delete_response = client.delete(f"/parts/{part_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Part deleted"


def test_create_part_with_invalid_supplier_fails(client):
    payload = {
        "sku": "PART-BAD-01",
        "part_name": "Bad Supplier Part",
        "category": "Electrical",
        "supplier_id": "SUP-NOT-EXIST",
        "unit_price": 50.0,
        "lead_time_days": 3,
        "criticality": 2,
    }

    response = client.post("/parts", json=payload)

    assert response.status_code == 400
    assert "Invalid supplier_id" in response.json()["detail"]
