# Database Structure

## Overview

The backend uses SQLite. The schema is defined in `backend/database/schema.sql`, and the local database file is created by `backend/scripts/init_db.py`.

The database has two jobs:

1. Support the operational API: users, auth, parts, stock, suppliers, orders, notifications, forecasts, and recommendations.
2. Preserve CSV-driven analytical data from `data/raw`: sales, weather, calendar, inventory snapshots, location metadata, and the dataset dictionary.

Seed flow:

1. `python scripts/init_db.py` applies `database/schema.sql`. By default it does not delete the existing SQLite file.
2. `python scripts/seed_data.py` safely refreshes CSV data from project-level `data/raw`.
3. The seed also creates missing initial auth data: roles plus an admin user.

Reset flow:

1. `python scripts/init_db.py --reset` deletes and recreates `backend/database/stock_optimizer.db`.
2. `python scripts/seed_data.py --reset` clears seeded/runtime tables and loads a clean development dataset.

Default refresh behavior preserves operational data:

- Existing `users`, `user_location_scope`, `user_stock`, `order_clients`, `order_suppliers`, `notifications`, `forecasts`, and `recommendations` are kept.
- Existing `stock.current_stock` is kept, so accepted client orders and received supplier orders are not undone by a CSV refresh.
- New CSV part/location stock rows are inserted with their CSV quantity.
- CSV-derived analytical tables are reloaded to avoid duplicate raw rows.

## Data Sources

Core CSV files used by the seed script:

| CSV file | Main target table(s) | Notes |
|---|---|---|
| `eu_locations.csv` | `eu_locations` | Source of location metadata such as city, country, climate, and payday rules. |
| `suppliers.csv` | `suppliers` | Supplier master data. `supplier_id` becomes `suppliers.id`. |
| `parts_master.csv` | `parts` | Parts catalog. `unit_price_eur` becomes `parts.unit_price`. |
| `inventory_snapshot.csv` | `inventory_snapshot`, `stock` | Keeps full raw snapshot and creates the operational current-stock table. |
| `sales_history.csv` | `sales_history`, `demand_history` | Keeps full raw history and creates a simplified demand table. |
| `weather_daily.csv` | `weather_daily` | Daily weather features by location. |
| `calendar_daily.csv` | `calendar_daily` | Dense daily calendar and event flags. |
| `calendar_events.csv` | `calendar_events` | Event-focused calendar rows. |
| `dataset_dictionary.csv` | `dataset_dictionary` | Human-readable descriptions for dataset columns. |

`data/raw/by_location/*.csv` contains location-specific sales slices. The backend seed currently uses the combined `sales_history.csv`.

## Table Groups

| Group | Tables | Purpose |
|---|---|---|
| Security and access | `roles`, `users`, `user_location_scope`, `audit_log` | Authentication, authorization, location permissions, and traceability. |
| Master data | `eu_locations`, `suppliers`, `parts` | Stable reference entities used by inventory and analytics. |
| Inventory operations | `stock`, `user_stock`, `inventory_snapshot`, `order_clients`, `order_client_lines`, `order_suppliers`, `order_supplier_lines`, `demand_history` | Imported/admin inventory, user-owned store stock, raw inventory snapshots, workflow orders, and simplified demand history. |
| Raw analytical layer | `sales_history`, `weather_daily`, `calendar_daily`, `calendar_events`, `dataset_dictionary` | CSV-aligned historical and exogenous features for analysis or ML. |
| Planning outputs | `forecasts`, `forecast_actuals`, `recommendations`, `notifications` | Model outputs, measured actuals, suggested actions, and operational warnings. |

## Relationship Summary

| From | To | Delete behavior | Meaning |
|---|---|---|---|
| `users.role_id` | `roles.id` | `RESTRICT` | A user must have a valid role. |
| `users.supplier_id` | `suppliers.id` | `SET NULL` | Optional supplier association can be removed without deleting user. |
| `user_location_scope.user_id` | `users.id` | `CASCADE` | User location permissions are deleted with the user. |
| `audit_log.user_id` | `users.id` | `SET NULL` | Audit history survives if a user is removed. |
| `parts.supplier_id` | `suppliers.id` | `RESTRICT` | A supplier cannot be removed while parts reference it. |
| `stock.part_id` | `parts.id` | `CASCADE` | Stock rows are deleted when a part is deleted. |
| `user_stock.user_id` | `users.id` | `CASCADE` | A user's store stock is deleted with the user. |
| `user_stock.part_id` | `parts.id` | `CASCADE` | User stock rows are deleted when a catalog part is deleted. |
| `demand_history.part_id` | `parts.id` | `CASCADE` | Simplified demand rows are deleted with the part. |
| `sales_history.part_id` | `parts.id` | `SET NULL` | Raw sales history survives even if a part row is removed. |
| `order_clients.user_id` | `users.id` | `SET NULL` | Client order history survives if the user is removed. |
| `order_suppliers.user_id` | `users.id` | `SET NULL` | Supplier order history survives if the user is removed. |
| `order_client_lines.part_id` | `parts.id` | `RESTRICT` | Ordered parts cannot be deleted while client orders reference them. |
| `order_supplier_lines.part_id` | `parts.id` | `RESTRICT` | Ordered parts cannot be deleted while supplier orders reference them. |
| `forecasts.part_id` | `parts.id` | `CASCADE` | Forecasts are deleted with the part. |
| `recommendations.part_id` | `parts.id` | `CASCADE` | Recommendations are deleted with the part. |
| `notifications.part_id` | `parts.id` | `CASCADE` | Notifications are deleted with the part. |
| `forecast_actuals.forecast_id` | `forecasts.id` | `CASCADE` | Actuals are deleted with their forecast. |

## Detailed Table Guide

### `roles`

Stores application roles such as `admin` and `user`.

What it does:

- Defines which broad permission level a user has.
- Keeps role names unique.
- Is seeded automatically by `seed_data.py`.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Internal numeric role ID. |
| `role_name` | `TEXT UNIQUE NOT NULL` | Stable role label, for example `admin` or `user`. |
| `description` | `TEXT` | Human-readable explanation of the role. |

Used by:

- `users.role_id`
- `app.core.auth.require_admin`
- `app.core.auth.require_authenticated_user`

### `users`

Stores user accounts.

What it does:

- Holds login identity and bcrypt password hash.
- Links every user to a role.
- Supports optional supplier association for supplier-related workflows.
- Supports user status workflows such as active, pending approval, and rejected.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Internal user ID. |
| `username` | `TEXT UNIQUE NOT NULL` | Login username. |
| `email` | `TEXT UNIQUE NOT NULL` | User email. |
| `password_hash` | `TEXT NOT NULL` | Bcrypt password hash, never plaintext. |
| `role_id` | `INTEGER NOT NULL` | FK to `roles.id`. |
| `supplier_id` | `TEXT` | Optional FK to `suppliers.id`. |
| `supplier_name_requested` | `TEXT` | Optional supplier name entered/requested during onboarding. |
| `status` | `TEXT NOT NULL` | Must be `active`, `pending_approval`, or `rejected`. |
| `is_active` | `BOOLEAN NOT NULL` | Fast account enable/disable flag. |
| `created_at` | `TEXT NOT NULL` | Creation timestamp. |
| `updated_at` | `TEXT NOT NULL` | Last update timestamp. |

Used by:

- Auth endpoints: `/auth/register`, `/auth/login`, `/auth/me`
- JWT current-user resolution
- `order_clients.user_id`
- `order_suppliers.user_id`
- `audit_log.user_id`
- `user_location_scope.user_id`

### `user_location_scope`

Stores which locations a normal user is allowed to see.

What it does:

- Restricts `GET /stock` and `GET /parts` for users with role `user`.
- Uses `location_id` as the stable permission key.
- Keeps `location` as display/backward-compatible text.
- Auto-assigns a deterministic default location if a user has no scope yet.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `user_id` | `INTEGER NOT NULL` | FK to `users.id`. |
| `location_id` | `TEXT NOT NULL` | Stable location code, for example `RO_BUC`. |
| `location` | `TEXT` | Display location, for example `Bucharest`. |
| `created_at` | `TEXT NOT NULL` | Assignment timestamp. |

Primary key:

- `(user_id, location_id)`, so a user cannot have the same location scope twice.

Used by:

- `app.core.user_scope`
- `app.core.auth`
- Inventory filtering in `parts.py` and `stock.py`

Important detail:

- `location_id` comes from `stock.location_id`, which is imported from `inventory_snapshot.csv`.

### `audit_log`

Stores a lightweight trail of actions.

What it does:

- Provides a place to record important changes or admin actions.
- Keeps user reference nullable so historical logs remain if a user is removed.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Audit event ID. |
| `user_id` | `INTEGER` | Optional FK to `users.id`. |
| `action` | `TEXT NOT NULL` | Action name, for example `create_part`. |
| `table_name` | `TEXT` | Table affected by the action. |
| `record_id` | `INTEGER` | Numeric record affected, when applicable. |
| `details` | `TEXT` | Free-form extra detail, often JSON text. |
| `created_at` | `TEXT NOT NULL` | Event timestamp. |

Used by:

- Future traceability/admin workflows.

### `eu_locations`

Stores location metadata for the European network.

What it does:

- Defines the canonical set of operating locations.
- Gives human-readable city/country details for each `location_id`.
- Provides weather/climate and payday metadata used by generated demand features.

CSV source:

- `data/raw/eu_locations.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `location_id` | `TEXT PRIMARY KEY` | Stable location code, for example `RO_BUC`. |
| `city` | `TEXT NOT NULL` | City name. |
| `country` | `TEXT NOT NULL` | Country name. |
| `country_code` | `TEXT NOT NULL` | ISO-like country code. |
| `timezone` | `TEXT` | Location timezone. |
| `latitude`, `longitude` | `REAL` | Geographic coordinates. |
| `climate_zone` | `TEXT` | Climate grouping used in demand/weather analysis. |
| `demand_scale` | `REAL` | Relative location demand multiplier. |
| `temp_mean_c` | `REAL` | Average temperature baseline. |
| `temp_amplitude_c` | `REAL` | Seasonal temperature swing. |
| `winter_start_month`, `winter_end_month` | `INTEGER` | Winter season boundaries. |
| `salary_days` | `TEXT` | Salary/payday rule source text. |
| `payday_last_business_day` | `INTEGER` | Whether payday is last business day. |

Used by:

- Location validation and display
- User scope display enrichment
- Weather/calendar/sales analytical features

### `suppliers`

Stores supplier master data and supplier performance metrics.

What it does:

- Is the source of truth for supplier identity.
- Links suppliers to parts.
- Stores simple delivery reliability metrics used by UI/API responses.

CSV source:

- `data/raw/suppliers.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `TEXT PRIMARY KEY` | Supplier ID from CSV, for example `SUP-FLUIDS-EU`. |
| `supplier_code` | `TEXT UNIQUE NOT NULL` | Stable supplier code. Currently same value as `id` during seed. |
| `supplier_name` | `TEXT UNIQUE NOT NULL` | Display name. |
| `country_code` | `TEXT` | Supplier country code. |
| `reliability_score` | `REAL` | Raw reliability score from CSV. |
| `avg_delay_days` | `REAL` | Average delay in days. |
| `avg_on_time_rate` | `REAL NOT NULL` | Normalized on-time rate from 0 to 1. |
| `default_lead_time_days` | `REAL NOT NULL` | Default lead time used as fallback. |
| `updated_at` | `TEXT NOT NULL` | Last seed/update timestamp. |

Used by:

- `parts.supplier_id`
- `order_suppliers.supplier_id`
- Enriched parts/stock/recommendation/alert responses

### `parts`

Stores the parts catalog.

What it does:

- Defines every sellable/service part by SKU.
- Connects each part to one supplier.
- Stores business inputs used by inventory and forecasting, such as base demand, seasonality, lead time, and minimum order quantity.

CSV source:

- `data/raw/parts_master.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Internal numeric part ID. |
| `sku` | `TEXT UNIQUE NOT NULL` | External stock keeping unit. |
| `part_name` | `TEXT NOT NULL` | Human-readable part name. |
| `category` | `TEXT NOT NULL` | Part category, for example brakes or fluids. |
| `seasonality_profile` | `TEXT` | Seasonal demand profile. |
| `base_demand` | `REAL` | Baseline demand estimate. |
| `supplier_id` | `TEXT NOT NULL` | FK to `suppliers.id`. |
| `unit_price` | `REAL NOT NULL` | Unit price, mapped from `unit_price_eur`. |
| `salary_sensitivity` | `REAL` | Demand sensitivity around salary/payday effects. |
| `lead_time_days` | `INTEGER NOT NULL` | Expected lead time for this part. |
| `min_order_qty` | `INTEGER` | Minimum order quantity. |
| `criticality` | `INTEGER NOT NULL` | Business criticality from 1 to 5. |

Used by:

- `stock`
- `user_stock`
- `demand_history`
- `sales_history`
- `forecasts`
- `recommendations`
- `notifications`
- `/parts`

### `user_stock`

Stores each normal user's own store stock against the admin parts catalog.

What it does:

- Lets every user track the quantity they personally have for each catalog part.
- Keeps user-edited stock separate from CSV/imported admin stock.
- Powers `GET /stock` for normal users.
- Feeds `/parts/catalog` so catalog parts with no user row still appear with quantity `0`.
- Is updated by supplier-order receiving and client-order allocation.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Internal user stock row ID. |
| `user_id` | `INTEGER NOT NULL` | FK to `users.id`. |
| `part_id` | `INTEGER NOT NULL` | FK to `parts.id`. |
| `location` | `TEXT NOT NULL` | User/store display location. |
| `location_id` | `TEXT` | Optional stable store/location key. |
| `current_stock` | `INTEGER NOT NULL` | User's current on-hand quantity. |
| `reorder_point` | `INTEGER NOT NULL` | User's reorder threshold. |
| `safety_stock` | `INTEGER NOT NULL` | User's buffer stock. |
| `optimal_stock` | `INTEGER NOT NULL` | User's target/recommended quantity. |
| `min_order_qty` | `INTEGER` | Optional minimum order quantity for this user's stock row. |
| `lead_time_days` | `INTEGER` | Optional lead time snapshot. |
| `pending_order_qty` | `INTEGER NOT NULL` | Quantity already pending in supplier orders. |
| `notes` | `TEXT` | Optional user note. |
| `created_at` | `TEXT NOT NULL` | Creation timestamp. |
| `updated_at` | `TEXT NOT NULL` | Last update timestamp. |

### `stock`

Stores the current operational stock state by part and location.

What it does:

- Powers the main stock API.
- Holds current stock, policy thresholds, and historical summary signals.
- Is derived from `inventory_snapshot.csv` during seed.
- Uses `location_id` for stable permissions/filtering, while keeping `location` for display/backward compatibility.

CSV source:

- Derived from `data/raw/inventory_snapshot.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `part_id` | `INTEGER NOT NULL` | FK to `parts.id`. |
| `location` | `TEXT NOT NULL` | Display/backward-compatible location, currently seeded from city. |
| `location_id` | `TEXT` | Stable location code, for example `RO_BUC`. |
| `city` | `TEXT` | City display value. |
| `country_code` | `TEXT` | Country code. |
| `current_stock` | `INTEGER NOT NULL` | Current on-hand quantity. |
| `reorder_point` | `INTEGER NOT NULL` | Threshold where replenishment should be considered. |
| `safety_stock` | `INTEGER NOT NULL` | Buffer stock. |
| `optimal_stock` | `INTEGER NOT NULL` | Target stock level, must be at least safety stock. |
| `min_order_qty` | `INTEGER` | Minimum order size for this part/location. |
| `lead_time_days` | `INTEGER` | Local lead-time value. |
| `pending_order_qty` | `INTEGER` | Quantity already ordered but not yet received. |
| `stockout_days_history` | `INTEGER` | Historical days with stockout. |
| `total_sales_history` | `INTEGER` | Historical sales summary. |
| `latent_demand_signal_history` | `REAL` | Historical latent demand signal. |
| `inventory_status` | `TEXT` | Status label, for example low/ok/overstock. |
| `avg_daily_demand_30d` | `REAL NOT NULL` | Recent demand average used by API logic. |
| `last_updated` | `TEXT NOT NULL` | Last stock update timestamp. |

Primary key:

- `(part_id, location)`

Important detail:

- Even though permissions use `location_id`, the current primary key still uses `(part_id, location)` for compatibility.
- `PATCH /stock/{part_id}/{location}` accepts either display `location` or `location_id`.

Used by:

- `/stock`
- `/parts` user filtering
- `user_location_scope` default assignment
- Ordering/replenishment workflows

### `inventory_snapshot`

Stores the raw inventory snapshot imported from CSV.

What it does:

- Preserves the source snapshot exactly in database form.
- Lets the backend retain more raw detail than the operational `stock` table.
- Feeds the operational `stock` table during seed.

CSV source:

- `data/raw/inventory_snapshot.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Internal row ID. |
| `snapshot_timestamp`, `snapshot_timestamp_utc`, `snapshot_date` | `TEXT` | Snapshot time in local/UTC/date forms. |
| `location_id`, `city`, `country_code` | `TEXT` | Location identity and display fields. |
| `sku`, `part_name`, `category` | `TEXT` | Part identity copied from snapshot. |
| `supplier_id` | `TEXT` | Supplier ID copied from snapshot. |
| `current_stock` | `INTEGER` | On-hand stock at snapshot time. |
| `reorder_point` | `INTEGER` | Reorder threshold at snapshot time. |
| `safety_stock` | `INTEGER` | Safety stock at snapshot time. |
| `optimal_stock` | `INTEGER` | Target stock at snapshot time. |
| `min_order_qty` | `INTEGER` | Minimum order quantity. |
| `lead_time_days` | `INTEGER` | Snapshot lead time. |
| `pending_order_qty` | `INTEGER` | Pending order quantity. |
| `stockout_days_history` | `INTEGER` | Historical stockout days. |
| `total_sales_history` | `INTEGER` | Historical sales quantity. |
| `latent_demand_signal_history` | `REAL` | Historical latent demand signal. |
| `inventory_status` | `TEXT` | Raw inventory status label. |

Used by:

- Audit/inspection of source inventory state
- Rebuilding the operational `stock` table during seed

### `demand_history`

Stores a simplified demand history table for API and forecasting workflows.

What it does:

- Provides a compact historical demand table with part, date, location, and quantity.
- Is derived from `sales_history.csv` during seed.
- Is easier for simple API and model calls than the very wide `sales_history` table.

CSV source:

- Derived from `data/raw/sales_history.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Demand row ID. |
| `part_id` | `INTEGER NOT NULL` | FK to `parts.id`. |
| `sale_date` | `TEXT NOT NULL` | Sale date. |
| `location` | `TEXT NOT NULL` | Location code or display value. Seed uses `location_id`. |
| `location_type` | `TEXT NOT NULL` | Type label, currently seeded as `location`. |
| `sales_quantity` | `INTEGER NOT NULL` | Quantity sold/used, must be non-negative. |

Used by:

- `/demand-history` endpoints
- Simple demand summaries
- Future forecasting inputs

### `sales_history`

Stores the full raw historical sales panel.

What it does:

- Preserves detailed demand history with product, location, date, weather, calendar, promotion, fuel, mobility, and generated demand-signal fields.
- Is the richest table for analytics/ML.
- Keeps rows even if `parts.id` is later removed, because `part_id` is nullable with `ON DELETE SET NULL`.

CSV source:

- `data/raw/sales_history.csv`

Column groups:

| Group | Columns | Purpose |
|---|---|---|
| Time identity | `timestamp`, `timestamp_utc`, `date` | Time of the sales observation. |
| Product identity | `sku`, `part_id`, `part_name`, `category`, `seasonality_profile` | Product identifiers and category features. |
| Location identity | `location_id`, `city`, `country`, `country_code`, `climate_zone` | Where the sale happened. |
| Sales metrics | `quantity_sold`, `latent_demand_signal`, `unit_price_eur`, `revenue_eur`, `stock_on_hand_end`, `stockout_flag` | Demand, revenue, and stockout signals. |
| Calendar decomposition | `day_of_week`, `day_name`, `day_of_month`, `week_of_year`, `month`, `quarter`, `year`, `season`, `is_weekend` | Date features for modeling. |
| Weather features | `temperature_c`, `temp_change_1d_c`, `temp_change_3d_c`, `abs_temp_change_3d_c`, `rain_mm`, `snow_cm` | Weather values at location/date. |
| Weather flags | `cold_snap_flag`, `heatwave_flag`, `weather_spike_flag`, `temperature_drop_flag`, `temperature_rise_flag` | Weather event indicators. |
| Calendar/event flags | `is_payday`, `is_payday_window`, `is_holiday`, `is_school_holiday`, `event_name`, `event_type`, `affected_categories`, `event_multiplier`, `promotion_flag`, `service_campaign_flag` | Event and commercial signals. |
| External signals | `fuel_price_eur_l`, `mobility_index` | Macro/external demand drivers. |
| Model/debug signals | `mean_demand_before_stock`, `weather_spike_applied`, `salary_spike_applied`, `calendar_spike_applied` | Generated demand-construction features. |

Used by:

- Historical analytics
- ML training/backtesting
- Building `demand_history`

### `weather_daily`

Stores daily weather features by location.

What it does:

- Preserves weather data independent of sales rows.
- Allows weather to be joined to demand by `location_id` and `date`.
- Supports weather-driven demand analysis, such as cold snaps and heatwaves.

CSV source:

- `data/raw/weather_daily.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Internal row ID. |
| `timestamp`, `timestamp_utc`, `date` | `TEXT` | Time identity. |
| `location_id`, `city`, `country_code`, `climate_zone` | `TEXT` | Location identity and climate grouping. |
| `temperature_c` | `REAL` | Daily temperature. |
| `temp_change_1d_c`, `temp_change_3d_c`, `abs_temp_change_3d_c` | `REAL` | Temperature movement features. |
| `rain_mm`, `snow_cm` | `REAL` | Precipitation features. |
| `cold_snap_flag`, `heatwave_flag` | `INTEGER` | Extreme weather indicators. |
| `weather_spike_flag` | `INTEGER` | General weather-driven demand spike flag. |
| `temperature_drop_flag`, `temperature_rise_flag` | `INTEGER` | Directional temperature movement flags. |

Used by:

- Analytics and ML features
- Explaining demand changes

### `calendar_daily`

Stores dense daily calendar/event features by location.

What it does:

- Provides one calendar-feature row per date/location.
- Captures payday, holiday, school holiday, promotion, service campaign, and event signals.
- Can be joined to sales/demand by `location_id` and `date`.

CSV source:

- `data/raw/calendar_daily.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Internal row ID. |
| `timestamp`, `timestamp_utc`, `date` | `TEXT` | Time identity. |
| `location_id`, `city`, `country_code` | `TEXT` | Location identity. |
| `is_payday`, `is_payday_window` | `INTEGER` | Salary-cycle flags. |
| `is_holiday`, `is_school_holiday` | `INTEGER` | Holiday flags. |
| `event_name`, `event_type` | `TEXT` | Event description fields. |
| `affected_categories` | `TEXT` | Categories affected by event. |
| `event_multiplier` | `REAL` | Demand multiplier associated with event. |
| `promotion_flag` | `INTEGER` | Promotion indicator. |
| `service_campaign_flag` | `INTEGER` | Service campaign indicator. |

Used by:

- ML/calendar feature joins
- Demand explanation by event or payday

### `calendar_events`

Stores event-focused calendar rows.

What it does:

- Contains the same shape as `calendar_daily`, but represents the event-oriented dataset.
- Useful when analysis needs event rows rather than a dense daily calendar table.

CSV source:

- `data/raw/calendar_events.csv`

Columns:

The columns match `calendar_daily`:

- time: `timestamp`, `timestamp_utc`, `date`
- location: `location_id`, `city`, `country_code`
- flags: `is_payday`, `is_payday_window`, `is_holiday`, `is_school_holiday`
- event and commercial fields: `event_name`, `event_type`, `affected_categories`, `event_multiplier`, `promotion_flag`, `service_campaign_flag`

Used by:

- Event-specific analytics
- Calendar/event feature exploration

### `dataset_dictionary`

Stores documentation for source dataset columns.

What it does:

- Makes the CSV schema self-describing inside the database.
- Helps developers and analysts understand what source columns mean.

CSV source:

- `data/raw/dataset_dictionary.csv`

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Dictionary row ID. |
| `file` | `TEXT` | Source file name. |
| `column_name` | `TEXT` | Column name. Mapped from CSV field `column`. |
| `description` | `TEXT` | Human-readable description. |

Used by:

- Data documentation
- Future UI/tooling that explains raw dataset columns

### `forecasts`

Stores model or algorithmic demand forecasts.

What it does:

- Records predicted demand for a part over a horizon.
- Keeps confidence and generation timestamp.
- Can later be compared against actual demand through `forecast_actuals`.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Forecast ID. |
| `part_id` | `INTEGER NOT NULL` | FK to `parts.id`. |
| `forecast_date` | `TEXT` | Date the forecast targets or starts. |
| `horizon_days` | `INTEGER NOT NULL` | Forecast horizon; must be greater than 0. |
| `predicted_demand` | `INTEGER NOT NULL` | Predicted demand; must be non-negative. |
| `confidence_score` | `REAL NOT NULL` | Confidence from 0 to 1. |
| `generated_at` | `TEXT NOT NULL` | Generation timestamp. |

Used by:

- `/forecasts`
- `/forecasts/{part_id}`
- `forecast_actuals`

### `recommendations`

Stores suggested inventory actions.

What it does:

- Represents recommended actions such as ordering, reducing, or transferring stock.
- Stores quantity and reason text for planner review.
- Supports transfer recommendations through source and target locations.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Recommendation ID. |
| `part_id` | `INTEGER NOT NULL` | FK to `parts.id`. |
| `action` | `TEXT NOT NULL` | Must be `order`, `reduce`, or `transfer`. |
| `quantity` | `INTEGER NOT NULL` | Recommended quantity, non-negative. |
| `source_location` | `TEXT` | Source location for transfer/reduction. |
| `target_location` | `TEXT` | Target location for transfer/order. |
| `reason` | `TEXT NOT NULL` | Human-readable explanation. |
| `created_at` | `TEXT NOT NULL` | Creation timestamp. |

Used by:

- Future recommendations endpoint/UI
- ML or rules-based replenishment decisions

### `notifications`

Stores operational warnings.

What it does:

- Captures inventory or planning issues that need attention.
- Supports severity levels for dashboard sorting.
- Links each alert to a part.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Alert ID. |
| `part_id` | `INTEGER NOT NULL` | FK to `parts.id`. |
| `severity` | `TEXT NOT NULL` | Must be `info`, `warning`, or `critical`. |
| `message` | `TEXT NOT NULL` | Alert text. |
| `created_at` | `TEXT NOT NULL` | Creation timestamp. |

Used by:

- Future notifications endpoint/UI
- Low stock, stockout, supplier, or forecast confidence warnings

### `forecast_actuals`

Stores measured actual demand for forecasts.

What it does:

- Closes the loop between predictions and reality.
- Lets the system calculate forecast accuracy after actual demand is known.
- References a specific forecast row.

Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Actual measurement ID. |
| `forecast_id` | `INTEGER NOT NULL` | FK to `forecasts.id`. |
| `actual_demand` | `INTEGER NOT NULL` | Observed demand, non-negative. |
| `measured_at` | `TEXT NOT NULL` | Measurement timestamp. |

Used by:

- Forecast evaluation
- Future accuracy dashboards

## Indexes

| Index | Columns | Why it exists |
|---|---|---|
| `idx_parts_sku` | `parts(sku)` | Fast lookup by SKU. |
| `idx_stock_location_id` | `stock(location_id)` | Fast location filtering and user scope queries. |
| `idx_sales_history_sku_date` | `sales_history(sku, date)` | Fast sales history lookup by product and date. |
| `idx_sales_history_location_date` | `sales_history(location_id, date)` | Fast location/date analytics. |
| `idx_demand_history_part_date` | `demand_history(part_id, sale_date)` | Fast demand history summaries by part/date. |

## Important Design Notes

### Supplier IDs are text-based

CSV supplier IDs are strings such as `SUP-FLUIDS-EU`, so:

- `suppliers.id` is `TEXT`
- `parts.supplier_id` is `TEXT`
- `inventory_snapshot.supplier_id` is `TEXT`
- `order_suppliers.supplier_id` is `TEXT`

This avoids fragile numeric remapping and keeps imported data readable.

### Location permissions use `location_id`

The stable location code is `location_id`, for example `RO_BUC`.

- `stock.location_id` is imported from `inventory_snapshot.csv`.
- `user_location_scope.location_id` controls normal-user visibility.
- `user_location_scope.location` is only display/backward-compatible text.
- `stock.location` currently remains part of the primary key for compatibility.

### Raw tables and operational tables are intentionally separate

`sales_history` and `inventory_snapshot` preserve source-like data.

`demand_history` and `stock` are simpler operational tables used by APIs.

This split lets the app stay ergonomic while still retaining rich analytical data.

## Expected Seed Counts

Current raw dataset seed scale:

| Table | Expected rows |
|---|---:|
| `roles` | 2 |
| `users` | 1 |
| `eu_locations` | 12 |
| `suppliers` | 8 |
| `parts` | 18 |
| `stock` | 216 |
| `inventory_snapshot` | 216 |
| `sales_history` | 236736 |
| `demand_history` | 236736 |
| `weather_daily` | 13512 |
| `calendar_daily` | 13512 |
| `calendar_events` | 9328 |
| `dataset_dictionary` | 11 |

## Maintenance Rules

- If `schema.sql` changes, update this document.
- If CSV headers change, update both `seed_data.py` and this document.
- Do not commit `backend/database/stock_optimizer.db`; it is generated locally.
- Prefer `location_id` for filtering, permissions, and joins.
- Keep raw analytical data in raw tables, and API-optimized data in operational tables.

