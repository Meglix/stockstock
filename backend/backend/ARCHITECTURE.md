# Backend Architecture - Frontend-Aligned Scope

## Goal

This backend is intentionally scoped to what the current frontend uses in production/demo flow:

- auth
- parts catalog
- user stock management
- order workflows
- dashboard summary analytics
- notifications feed
- health check

Anything outside this scope should be treated as future work and added only when a frontend flow requires it.

## Runtime Flow

1. `app/main.py` creates the FastAPI app and registers active routers only.
2. `app/db.py` provides SQLite connections with foreign keys enabled.
3. `app/core/auth.py` authenticates JWT users and applies role/scope checks.
4. Router handlers in `app/inventory` and `app/analytics` execute business logic and DB writes.
5. `scripts/init_db.py` ensures schema exists.
6. `scripts/seed_data.py` refreshes CSV-backed data without wiping user/runtime workflow tables by default.

## Active Package Layout

```text
backend/
  app/
    main.py
    db.py
    core/
      auth.py
      user_scope.py
    infrastructure/
      routers/
        auth.py
        health.py
    inventory/
      routers/
        orders.py
        parts.py
        stock.py
      schemas/
        orders.py
        parts.py
        stock.py
      services/
        order_access.py
        order_workflows.py
        parts_catalog.py
        user_stock.py
    analytics/
      routers/
        dashboard.py
        notifications.py
      services/
        dashboard.py
  database/
    schema.sql
    stock_optimizer.db
  scripts/
    init_db.py
    migrate_order_workflows.py
    seed_data.py
    view_db.py
  tests/
    conftest.py
    test_auth.py
    test_health.py
    test_parts.py
    test_stock.py
```

## Active Routers

Registered in `app/main.py`:

- `app.infrastructure.routers.auth`
- `app.infrastructure.routers.health`
- `app.inventory.routers.parts`
- `app.inventory.routers.stock`
- `app.inventory.routers.orders`
- `app.analytics.routers.dashboard`
- `app.analytics.routers.notifications`

## API Domains

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### Health

- `GET /health`

### Parts

- `GET /parts`
- `GET /parts/catalog`
- `GET /parts/catalog/filters`
- `GET /parts/catalog/{part_id}`
- `GET /parts/{part_id}`
- `POST /parts`
- `PATCH /parts/{part_id}`
- `DELETE /parts/{part_id}`

### Stock

- `GET /stock`
- `GET /stock/{part_id}`
- `POST /stock`
- `PATCH /stock/{part_id}/{location}`
- `DELETE /stock/{part_id}/{location}`

### Orders

- `GET /orders/clients`
- `POST /orders/clients`
- `POST /orders/clients/random`
- `GET /orders/clients/{order_id}/availability`
- `POST /orders/clients/{order_id}/approve`
- `POST /orders/clients/{order_id}/deny`
- `POST /orders/clients/{order_id}/schedule`
- `POST /orders/clients/{order_id}/complete`
- `GET /orders/suppliers`
- `POST /orders/suppliers`
- `POST /orders/suppliers/{order_id}/receive`
- `POST /orders/suppliers/{order_id}/postpone`
- `POST /orders/suppliers/{order_id}/refuse`

### Dashboard And Notifications

- `GET /dashboard/summary`
- `GET /dashboard/sales-flow`
- `GET /dashboard/market-trends`
- `GET /dashboard/supplier-locations`
- `GET /dashboard/priority-stock`
- `GET /notifications`

## Data Ownership

- Frontend owns UI state and calls `/api/...` routes only.
- Backend owns all inventory/order business rules and DB writes.
- Frontend does not read SQLite directly.

## Database Table Groups

### Runtime tables (active)

- `users`, `roles`, `user_location_scope`
- `parts`, `suppliers`, `stock`, `user_stock`
- `order_clients`, `order_client_lines`
- `order_suppliers`, `order_supplier_lines`
- `order_notification_stream`, `order_sales_events`
- `notifications`

### Historical and analytical source tables

- `sales_history`
- `inventory_snapshot`
- `weather_daily`
- `calendar_daily`
- `calendar_events`
- `dataset_dictionary`
- `eu_locations`
- `demand_history`
- `forecasts`, `forecast_actuals`, `recommendations`

Historical/analytical source tables are kept in schema for dataset continuity, but no dedicated API routers are exposed for them unless required by frontend.
