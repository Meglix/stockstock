# Backend -> ML API Map

Frontend should not call the ML service directly. The safe path is:

`frontend /api/...` -> `backend` -> `ML_SERVICE_BASE_URL`

The frontend uses `/api/ml/*` because `frontend/next.config.mjs` rewrites `/api/:path*` to the backend. The backend ML client defaults to `ML_SERVICE_BASE_URL=http://localhost:8001`.

## Response Envelope

Backend ML proxy responses are normalized:

```json
{
  "available": true,
  "source": "ml-service",
  "location_id": "RO_BUC",
  "items": [],
  "data": null,
  "error": null
}
```

List endpoints return rows in `items`. Object endpoints return the ML object in `data`.

## Proxy Endpoints

| Frontend/backend endpoint | ML endpoint | Used for |
| --- | --- | --- |
| `GET /ml/health` | `GET /health` | ML service/file health |
| `GET /ml/model/metadata` | `GET /model/metadata` | model metadata |
| `GET /ml/data/locations` | `GET /data/locations` | ML location catalog |
| `GET /ml/data/parts` | `GET /data/parts` | ML part catalog |
| `GET /ml/data/weather?location=RO_BUC` | `GET /data/weather?location_id=RO_BUC` | weather features |
| `GET /ml/data/events?location=RO_BUC` | `GET /data/events?location_id=RO_BUC` | calendar/event features |
| `GET /ml/data/sales-history?sku=...&location=RO_BUC` | `GET /data/sales-history?sku=...&location_id=RO_BUC` | actual demand history |
| `GET /ml/forecast/{sku}?location=RO_BUC&horizon=30` | `GET /forecast/{sku}?location_id=RO_BUC&horizon=30` | forecast chart |
| `GET /ml/segments?location=RO_BUC` | `GET /segments?location_id=RO_BUC` | demand clustering |
| `GET /ml/recommendations?location=RO_BUC` | `GET /recommendations?location_id=RO_BUC` | stock/order recommendations |
| `GET /ml/alerts?location=RO_BUC` | `GET /alerts?location_id=RO_BUC` | ML alerts |
| `GET /ml/decision/alerts?location=RO_BUC` | `GET /decision/alerts?location_id=RO_BUC` | dashboard demand signals |
| `GET /ml/decision/stock-risk?sku=...&location=RO_BUC` | `GET /decision/stock-risk?sku=...&location_id=RO_BUC` | optimal/recommended stock target |
| `GET /ml/decision/sensitivity-profiles` | `GET /decision/sensitivity-profiles` | product sensitivity |
| `GET /ml/decision/scenarios` | `GET /decision/scenarios` | forecast scenarios |
| `GET /ml/decision/map` | `GET /decision/map` | risk map |
| `GET /ml/decision/explainability` | `GET /decision/explainability` | alert explanation |
| `GET /ml/decision/model-monitoring` | `GET /decision/model-monitoring` | model monitoring |
| `GET /ml/decision/integrations` | `GET /decision/integrations` | data integration health |
| `GET /ml/kpis?horizon=30` | `GET /kpis?horizon=30` | ML KPIs |

Admin-only ML generation endpoints:

| Backend endpoint | ML endpoint |
| --- | --- |
| `POST /ml/decision/build?horizon=21` | `POST /decision/build?horizon=21` |
| `POST /ml/refresh-outputs` | `POST /refresh-outputs` |
| `POST /ml/retrain` | `POST /retrain` |

## Stock Recommendation Bridge

The stock screen uses backend stock endpoints, not direct ML endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /stock/{part_id}/ml-recommendation?location=RO_BUC` | Reads ML `/decision/stock-risk` first, then `/recommendations`, and returns a backend-friendly recommended stock target. |
| `POST /stock/{part_id}/apply-ml-recommendation?location=RO_BUC` | Applies the ML recommended stock target to `optimal_stock` and updates `reorder_point` when ML provides one. |

The backend response includes both the stock target and the order quantity:

```json
{
  "available": true,
  "source": "ml-service",
  "recommended_stock": 1000,
  "recommended_order_qty": 836,
  "reorder_point": 616,
  "priority": "high",
  "risk_status": "critical"
}
```

## Current Frontend Wiring

| Frontend area | Backend/ML source |
| --- | --- |
| Forecasting page chart | `/api/ml/data/sales-history` for actual demand plus `/api/ml/forecast/{sku}` for forecast demand |
| Forecasting page insight | `/api/ml/forecast/{sku}`, `/api/ml/recommendations`, `/api/ml/decision/alerts` |
| Dashboard demand forecast | `/api/ml/data/sales-history` plus `/api/ml/forecast/PEU-WINTER-TIRE-205` |
| Dashboard sales demand signals | `/api/ml/decision/alerts` and `/api/ml/recommendations` |
| Stock recommended quantity | `/api/stock/{part_id}/ml-recommendation` |
| Apply recommended stock | `/api/stock/{part_id}/apply-ml-recommendation` |

## Local Run

Run the services separately:

```powershell
cd ml
docker compose up --build
```

```powershell
cd backend/backend
py -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev
```

The ML container exposes `localhost:8001`, the backend runs on `localhost:8000`, and the frontend rewrites `/api/*` to the backend.
