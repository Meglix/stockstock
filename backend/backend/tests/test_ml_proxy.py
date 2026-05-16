import app.analytics.routers.ml as ml_router


def test_sales_history_uses_csv_fallback_when_ml_service_is_down(client, monkeypatch):
    def fake_safe_ml_service_get(path, params=None):
        assert path == "/data/sales-history"
        return ([], "connection failed")

    def fake_read_sales_history_csv(**kwargs):
        assert kwargs["sku"] == "PEU-BATT-70AH"
        assert kwargs["location_id"] == "DK_CPH"
        return (
            [
                {
                    "date": "2025-12-31",
                    "sku": "PEU-BATT-70AH",
                    "location_id": "DK_CPH",
                    "quantity_sold": "18",
                }
            ],
            None,
        )

    monkeypatch.setattr(ml_router, "safe_ml_service_get", fake_safe_ml_service_get)
    monkeypatch.setattr(ml_router, "read_sales_history_csv", fake_read_sales_history_csv)

    response = client.get("/ml/data/sales-history?sku=PEU-BATT-70AH&location=DK_CPH")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["source"] == "ml-csv-fallback"
    assert body["items"][0]["quantity_sold"] == "18"


def test_weather_uses_open_meteo_csv_fallback_when_ml_service_is_down(client, monkeypatch):
    def fake_safe_ml_service_get(path, params=None):
        assert path == "/weather/open-meteo"
        return ([], "connection failed")

    def fake_read_open_meteo_csv(**kwargs):
        assert kwargs["location_id"] == "FI_HEL"
        return (
            [
                {
                    "date": "2026-05-13",
                    "location_id": "FI_HEL",
                    "city": "Helsinki",
                    "temperature_c": "2.5",
                    "weather_source": "open_meteo_forecast",
                }
            ],
            None,
        )

    monkeypatch.setattr(ml_router, "safe_ml_service_get", fake_safe_ml_service_get)
    monkeypatch.setattr(ml_router, "read_open_meteo_csv", fake_read_open_meteo_csv)

    response = client.get("/ml/weather/live?location=FI_HEL")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["source"] == "open-meteo-csv-fallback"
    assert body["items"][0]["weather_source"] == "open_meteo_forecast"
