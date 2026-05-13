# Backend API Reference

Base URL in local development: `http://localhost:8000`

The frontend calls these through `/api/...`; Next.js rewrites `/api/:path*` to the backend URL. Example: frontend `GET /api/dashboard/summary` becomes backend `GET /dashboard/summary`.

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

## Frontend-Used Endpoints

These are the endpoints currently wired by the Next.js app.

| Area | Method | Backend path | Frontend path | Auth | Purpose |
|---|---:|---|---|---|---|
| Auth | GET | `/auth/locations` | `/api/auth/locations` | No | Return readable location labels plus `location_id` values for registration. |
| Auth | POST | `/auth/register` | `/api/auth/register` | No | Create user account. Payload uses `full_name`, `company`, `email`, `password`, `location_id`. |
| Auth | POST | `/auth/login` | `/api/auth/login` | No | Log in and return JWT plus user profile. |
| Auth | GET | `/auth/me` | `/api/auth/me` | Bearer | Validate the current session. |
| Parts | GET | `/parts/catalog` | `/api/parts/catalog` | Bearer | Catalog view for all orderable parts, enriched with the current user's stock where available. |
| Stock | GET | `/stock` | `/api/stock` | Bearer | Current user's own stock rows. Missing catalog parts appear as zero in the frontend catalog flow. |
| Stock | POST | `/stock` | `/api/stock` | Bearer | Create/update a user stock row. |
| Stock | PATCH | `/stock/{part_id}/{location}` | `/api/stock/{part_id}/{location}` | Bearer | Update current quantity and policy fields for one user stock row. |
| Stock | DELETE | `/stock/{part_id}/{location}` | `/api/stock/{part_id}/{location}` | Bearer | Remove one user stock row. |
| Dashboard | GET | `/dashboard/summary` | `/api/dashboard/summary` | Bearer | One payload for dashboard KPIs, monthly demand chart, demand signals, supplier map, and priority stock. |
| Dashboard | GET | `/dashboard/ml/forecast` | `/api/dashboard/ml/forecast` | Bearer | Bridge endpoint that fetches ML forecast rows without changing the existing dashboard summary contract. |
| Dashboard | GET | `/dashboard/ml/recommendations` | `/api/dashboard/ml/recommendations` | Bearer | Bridge endpoint that fetches ML replenishment recommendations. |
| Dashboard | GET | `/dashboard/ml/alerts` | `/api/dashboard/ml/alerts` | Bearer | Bridge endpoint that fetches ML/decision-layer alerts. |
| Dashboard | GET | `/dashboard/ml/kpis` | `/api/dashboard/ml/kpis` | Bearer | Bridge endpoint that fetches ML KPI aggregates. |
| Notifications | GET | `/notifications?generate=true` | `/api/notifications?generate=true` | Bearer | Generate timed demo workflow orders if due and return current notifications. |
| Orders | GET | `/orders/clients` | `/api/orders/clients` | Bearer | Client orders needing approval plus handled history. |
| Orders | GET | `/orders/suppliers` | `/api/orders/suppliers` | Bearer | Supplier orders and delivery confirmations. |
| Orders | POST | `/orders/suppliers` | `/api/orders/suppliers` | Bearer | Place a supplier order manually. |
| Orders | GET | `/orders/clients/{id}/availability` | `/api/orders/clients/{id}/availability` | Bearer | Preview whether stock can fulfill a client order. |
| Orders | POST | `/orders/clients/{id}/approve` | `/api/orders/clients/{id}/approve` | Bearer | Approve client order; allocates stock if available, otherwise creates backorder flow. |
| Orders | POST | `/orders/clients/{id}/deny` | `/api/orders/clients/{id}/deny` | Bearer | Refuse client order. |
| Orders | POST | `/orders/clients/{id}/schedule` | `/api/orders/clients/{id}/schedule` | Bearer | Postpone/schedule a client order. |
| Orders | POST | `/orders/clients/{id}/complete` | `/api/orders/clients/{id}/complete` | Bearer | Complete a ready/allocated client order and record sales events. |
| Orders | POST | `/orders/suppliers/{id}/receive` | `/api/orders/suppliers/{id}/receive` | Bearer | Confirm supplier delivery and add received quantities into user stock. |
| Orders | POST | `/orders/suppliers/{id}/postpone` | `/api/orders/suppliers/{id}/postpone` | Bearer | Postpone a supplier delivery. |
| Orders | POST | `/orders/suppliers/{id}/refuse` | `/api/orders/suppliers/{id}/refuse` | Bearer | Refuse a supplier delivery. |

## Full Active Endpoint List

Only routers registered in `app/main.py` are listed here.

### Auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/auth/locations` | No | Returns `locations` with `location_id`, `city`, `country`, `country_code`, and display `label`. |
| POST | `/auth/register` | No | Public user registration. Admins are provisioned separately. |
| POST | `/auth/login` | No | Returns `access_token`, `token_type`, and `user`. |
| GET | `/auth/me` | Bearer | Returns current user's profile. |

### Infrastructure

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | No | Health check. |

### Parts And Catalog

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/parts` | Bearer | Admin/imported parts list, scoped for normal users. |
| GET | `/parts/catalog` | Bearer | Frontend-ready catalog. Shows all available catalog parts. |
| GET | `/parts/catalog/filters` | Bearer | Filter values for the catalog UI. |
| GET | `/parts/catalog/{part_id}` | Bearer | Single catalog item. |
| GET | `/parts/{part_id}` | Bearer | Single raw part record. |
| POST | `/parts` | Admin | Create part. |
| PATCH | `/parts/{part_id}` | Admin | Update part. |
| DELETE | `/parts/{part_id}` | Admin | Delete part. |

### Stock

Normal users write to `user_stock`. Admins manage imported/admin `stock`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/stock` | Bearer | User's own stock rows for normal users. |
| GET | `/stock/{part_id}` | Bearer | Stock for one part. |
| POST | `/stock` | Bearer | Create/update user stock. |
| PATCH | `/stock/{part_id}/{location}` | Bearer | Update user stock or admin imported stock. |
| DELETE | `/stock/{part_id}/{location}` | Bearer | Delete user stock or admin imported stock. |

### Orders

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/orders/clients` | Bearer | Supports status/location filters. Seeds/release workflow records as needed. |
| POST | `/orders/clients` | Bearer | Create client order manually. |
| POST | `/orders/clients/random` | Bearer | Generate one demo client order. |
| GET | `/orders/clients/{order_id}/availability` | Bearer | Returns stock availability preview. |
| POST | `/orders/clients/{order_id}/approve` | Bearer | Approve and allocate stock, or create backorder replenishment. |
| POST | `/orders/clients/{order_id}/deny` | Bearer | Refuse client order. |
| POST | `/orders/clients/{order_id}/schedule` | Bearer | Body uses `time` in `HH:MM`. |
| POST | `/orders/clients/{order_id}/complete` | Bearer | Finalize fulfilled order and write `order_sales_events`. |
| GET | `/orders/suppliers` | Bearer | Supports status/location filters. |
| POST | `/orders/suppliers` | Bearer | Create supplier order manually. |
| POST | `/orders/suppliers/{order_id}/receive` | Bearer | Add delivered parts into stock. |
| POST | `/orders/suppliers/{order_id}/postpone` | Bearer | Body uses `time` in `HH:MM`. |
| POST | `/orders/suppliers/{order_id}/refuse` | Bearer | Refuse supplier delivery. |

### Dashboard And Analytics

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/dashboard/summary` | Bearer | Dashboard aggregate payload used by frontend. |
| GET | `/dashboard/sales-flow?months=6&categories=6&category=...` | Bearer | Monthly demand/sales flow. Runtime order sales are preferred; CSV sales history is fallback. |
| GET | `/dashboard/market-trends?limit=5` | Bearer | Demand signals derived from recent sales movement until ML forecasting is added. |
| GET | `/dashboard/supplier-locations?limit=8` | Bearer | Supplier map markers from supplier/catalog data. |
| GET | `/dashboard/priority-stock?limit=5` | Bearer | Manager action list. |
| GET | `/dashboard/ml/forecast?sku=...&location=FI_HEL&horizon=30` | Bearer | Non-breaking ML bridge. Uses the user's default `location_id` when no override is supplied. |
| GET | `/dashboard/ml/recommendations?action=order&priority=high&location=FI_HEL` | Bearer | Non-breaking ML bridge for replenishment recommendations. |
| GET | `/dashboard/ml/alerts?priority=high&location=FI_HEL` | Bearer | Non-breaking ML bridge for ML/decision-layer alert rows. |
| GET | `/dashboard/ml/kpis?horizon=30` | Bearer | Non-breaking ML bridge for aggregate ML metrics. |
| GET | `/notifications?generate=true` | Bearer | Workflow notifications; `generate=true` allows one timed demo order when due. |

## ML Bridge Notes

- Existing frontend-connected endpoints remain unchanged.
- The `/dashboard/ml/*` routes are additive and safe to adopt incrementally.
- Backend talks to the ML FastAPI service through `ML_SERVICE_BASE_URL`.
- If the ML service is unavailable, these endpoints return a successful payload with `available = false` and an error string instead of breaking the dashboard.

## Runtime Tables Used By Current Frontend

| Table | Role |
|---|---|
| `users`, `roles` | Auth and user identity. |
| `parts`, `suppliers`, `stock` | Imported/admin catalog baseline from CSV seed data. |
| `user_stock` | Per-user stock quantities and thresholds. |
| `order_clients`, `order_client_lines` | Client demand/order workflow. |
| `order_suppliers`, `order_supplier_lines` | Supplier replenishment and delivery workflow. |
| `order_notification_stream` | Per-user timed demo order stream control. |
| `order_sales_events` | Completed client order sales, used by dashboard demand history before falling back to CSV sales history. |
| `notifications` | Stock/alert rows. ML-generated notifications can be added here later. |

## Separation Rules

- Backend owns data rules, stock updates, order status changes, backorder behavior, and DB writes.
- Frontend owns UI state, layout, forms, and calling `/api/...`.
- Frontend should not import backend code or read SQLite directly.
- Backend should not depend on frontend files or assets.
