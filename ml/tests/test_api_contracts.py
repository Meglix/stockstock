from fastapi.testclient import TestClient

import app.main as main_module


def test_forecast_endpoint_slices_default_30d_artifact_for_short_horizon(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()
    (processed_dir / "forecast_30d.csv").write_text(
        "\n".join(
            [
                "forecast_date,horizon_day,sku,location_id,predicted_quantity,predicted_revenue_eur",
                "2026-01-01,1,SKU-1,LOC-1,4.5,10",
                "2026-01-02,2,SKU-1,LOC-1,5.5,12",
                "2026-01-08,8,SKU-1,LOC-1,9.5,20",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(main_module, "DATA_RAW_DIR", raw_dir)
    monkeypatch.setattr(main_module, "DATA_PROCESSED_DIR", processed_dir)
    monkeypatch.setattr(main_module, "DEFAULT_FORECAST_HORIZON", 30)

    response = TestClient(main_module.app).get("/forecast", params={"sku": "SKU-1", "location_id": "LOC-1", "horizon": 7})

    assert response.status_code == 200
    rows = response.json()
    assert [row["horizon_day"] for row in rows] == [1, 2]


def test_sales_history_endpoint_returns_latest_rows_sorted(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()
    (raw_dir / "sales_history.csv").write_text(
        "\n".join(
            [
                "date,sku,location_id,quantity_sold",
                "2026-01-01,SKU-1,LOC-1,2",
                "2026-01-03,SKU-1,LOC-1,6",
                "2026-01-02,SKU-1,LOC-1,4",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(main_module, "DATA_RAW_DIR", raw_dir)
    monkeypatch.setattr(main_module, "DATA_PROCESSED_DIR", processed_dir)

    response = TestClient(main_module.app).get("/data/sales-history", params={"sku": "SKU-1", "location_id": "LOC-1", "limit": 2})

    assert response.status_code == 200
    rows = response.json()
    assert [row["date"] for row in rows] == ["2026-01-02", "2026-01-03"]
