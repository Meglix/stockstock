# Backend - Stock Optimizer Automotive

## Overview

The backend provides the API and database layer for the Stock Optimizer demo.

It uses FastAPI, SQLite, JWT authentication, and project-level CSV datasets for initial catalog, stock, supplier, and analytical history data.

The frontend should talk to this backend through relative `/api/...` calls. The frontend rewrite maps those calls to the backend server, so the frontend does not need to import backend files or read SQLite directly.

## Current Scope

- Manage the database structure through `database/schema.sql`
- Seed initial data from `data/raw` CSV files
- Register and authenticate users
- Serve catalog, user stock, order workflow, notifications, and dashboard APIs
- Preserve live demo data across restarts unless a reset is explicitly requested

## ML Integration Status

- The backend does not train ML models itself.
- The backend now supports additive ML bridge endpoints that can call the separate ML FastAPI service.
- Existing frontend-connected endpoints remain unchanged; ML integration is opt-in through new routes.

## Tech Stack

```text
Python
FastAPI
SQLite
Uvicorn
bcrypt
python-jose
```

## Security

### Passwords

- Passwords are hashed with bcrypt.
- Plaintext passwords are never stored.

### Environment

- Store secrets in `.env`, created from `.env.example` when needed.
- Do not commit `.env`.
- Important keys:
  - `JWT_SECRET_KEY`
  - `INITIAL_ADMIN_PASSWORD`

### Authentication

- Login returns a JWT bearer token.
- Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

## Authentication API

### Register

```http
POST /auth/register
```

```json
{
  "full_name": "Jane Doe",
  "company": "Acme Corp",
  "email": "jane@example.com",
  "password": "mypassword",
  "location_id": "FI_HEL"
}
```

Password must have at least 8 characters and include uppercase, number, and special character.

Available registration locations are returned by:

```http
GET /auth/locations
```

The response contains readable city/country labels for display and `location_id` values for submission/storage.

### Login

```http
POST /auth/login
```

```json
{
  "email": "jane@example.com",
  "password": "mypassword"
}
```

Returns `access_token`, `token_type`, and the current user profile.

### Current User

```http
GET /auth/me
Authorization: Bearer <access_token>
```

### Seeded Admin

- Email: `admin@stockoptimizer.local`
- Password: value of `INITIAL_ADMIN_PASSWORD`

## Folder Structure

The backend is organized by business domain, not by file type.

```text
backend/
|-- app/
|   |-- main.py
|   |-- db.py
|   |-- core/
|   |   |-- auth.py
|   |   `-- user_scope.py
|   |-- infrastructure/
|   |   `-- routers/
|   |       |-- auth.py
|   |       `-- health.py
|   |-- inventory/
|   |   |-- routers/
|   |   |   |-- orders.py
|   |   |   |-- parts.py
|   |   |   `-- stock.py
|   |   |-- schemas/
|   |   `-- services/
|   `-- analytics/
|       |-- routers/
|       |   |-- dashboard.py
|       |   `-- notifications.py
|       `-- services/
|-- database/
|   |-- schema.sql
|   `-- stock_optimizer.db
|-- scripts/
|   |-- init_db.py
|   |-- seed_data.py
|   |-- view_db.py
|   `-- migrate_order_workflows.py
|-- API.md
|-- requirements.txt
`-- README.md
```

## Organization Rules

- `app/core` owns shared authentication and scope helpers.
- `app/infrastructure` owns infrastructure endpoints such as auth and health.
- `app/inventory` owns parts, stock, and orders.
- `app/analytics` owns dashboard and notification APIs.
- `database/schema.sql` owns the database table definitions.
- `scripts` owns local setup, seed, migration, and inspection scripts.

## Database

The active database file is:

```text
backend\database\stock_optimizer.db
```

The backend should not use older database copies from `AppData`, downloads, or other folders.

### Active Runtime Tables

These tables are used by the current frontend and backend workflow:

- `users`
- `roles`
- `parts`
- `suppliers`
- `stock`
- `user_stock`
- `order_clients`
- `order_client_lines`
- `order_suppliers`
- `order_supplier_lines`
- `order_notification_stream`
- `order_sales_events`
- `notifications`
- `sales_history`

### Future Or Analytical Tables

These are mostly for CSV history, dashboard fallback, or future ML/forecasting work:

- `inventory_snapshot`
- `demand_history`
- `weather_daily`
- `calendar_daily`
- `calendar_events`
- `dataset_dictionary`
- `forecasts`
- `forecast_actuals`
- `recommendations`
- `eu_locations`
- `audit_log`
- `user_location_scope`

## Data Source

Seed data comes from:

```text
data\raw
```

Expected CSV files include:

- `sales_history.csv`
- `parts_master.csv`
- `suppliers.csv`
- `inventory_snapshot.csv`
- `eu_locations.csv`
- `weather_daily.csv`
- `calendar_daily.csv`
- `calendar_events.csv`
- `dataset_dictionary.csv`

## Run Backend

Open PowerShell:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
py -m uvicorn app.main:app --reload
```

Backend URLs:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

## Initialize Or Refresh Data

The backend applies the schema automatically on startup without deleting data.

Manual schema apply:

```powershell
py scripts\init_db.py
```

Non-destructive CSV refresh:

```powershell
py scripts\seed_data.py
```

Full reset, only when you intentionally want a clean demo database:

```powershell
py scripts\init_db.py --reset
py scripts\seed_data.py --reset
```

## Data Persistence

Default startup behavior:

- `AUTO_BOOTSTRAP_DB=true`: apply schema automatically and seed only if the DB is missing or incomplete
- `RESET_DB_ON_START=false`: preserve users, stock edits, and workflow orders
- `REFRESH_CSV_ON_START=false`: avoid reloading large CSV-backed history tables on every start

If CSV files changed and you want a non-destructive refresh on startup:

```powershell
$env:REFRESH_CSV_ON_START="true"
py -m uvicorn app.main:app --reload
```

## Inspect Live Database

From the backend folder:

```powershell
py scripts\view_db.py
```

For a visual editor, open `database\stock_optimizer.db` with a SQLite viewer such as DB Browser for SQLite or a VS Code SQLite extension.

## Active API Docs

The full current API reference is in:

```text
backend/API.md
```

Short overview:

| Area | Main paths |
|---|---|
| Auth | `/auth/locations`, `/auth/register`, `/auth/login`, `/auth/me` |
| Parts | `/parts`, `/parts/catalog`, `/parts/catalog/filters` |
| Stock | `/stock`, `/stock/{part_id}`, `/stock/{part_id}/{location}` |
| Orders | `/orders/clients`, `/orders/suppliers` |
| Dashboard | `/dashboard/summary`, `/dashboard/sales-flow`, `/dashboard/ml/*` |
| Notifications | `/notifications` |
| Health | `/health` |

## ML Service Connection

Optional backend-to-ML bridge endpoints use the environment variable below:

- `ML_SERVICE_BASE_URL` (default: `http://localhost:8001`)

These bridge endpoints are additive and safe for the current frontend:

- `/dashboard/ml/forecast`
- `/dashboard/ml/recommendations`
- `/dashboard/ml/alerts`
- `/dashboard/ml/kpis`

## Frontend Connection

The active frontend folder is:

```text
..\frontend-master
```

The frontend uses relative API calls like:

```text
/api/auth/login
/api/dashboard/summary
/api/orders/clients
```

`frontend-master\next.config.mjs` rewrites those calls to the backend URL, usually:

```text
http://localhost:8000
```

## Quick Checks

Backend import check:

```powershell
py -B -c "from app.main import app; print('routes', len(app.routes))"
```

Database check:

```powershell
py scripts\view_db.py
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```
