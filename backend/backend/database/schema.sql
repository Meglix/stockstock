PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT,
    company TEXT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    location_id TEXT,
    password_hash TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS user_location_scope (
    user_id INTEGER NOT NULL,
    location_id TEXT NOT NULL,
    location TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, location_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    table_name TEXT,
    record_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS eu_locations (
    location_id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    country_code TEXT NOT NULL,
    timezone TEXT,
    latitude REAL,
    longitude REAL,
    climate_zone TEXT,
    demand_scale REAL,
    temp_mean_c REAL,
    temp_amplitude_c REAL,
    winter_start_month INTEGER,
    winter_end_month INTEGER,
    salary_days TEXT,
    payday_last_business_day INTEGER
);

CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    supplier_code TEXT NOT NULL UNIQUE,
    supplier_name TEXT NOT NULL UNIQUE,
    country_code TEXT,
    reliability_score REAL,
    avg_delay_days REAL,
    avg_on_time_rate REAL NOT NULL DEFAULT 0.9 CHECK (avg_on_time_rate >= 0 AND avg_on_time_rate <= 1),
    default_lead_time_days REAL NOT NULL DEFAULT 0 CHECK (default_lead_time_days >= 0),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    part_name TEXT NOT NULL,
    category TEXT NOT NULL,
    seasonality_profile TEXT,
    base_demand REAL,
    supplier_id TEXT,
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    salary_sensitivity REAL,
    lead_time_days INTEGER NOT NULL CHECK (lead_time_days >= 0),
    min_order_qty INTEGER,
    criticality INTEGER NOT NULL DEFAULT 3 CHECK (criticality >= 1 AND criticality <= 5),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS stock (
    part_id INTEGER NOT NULL,
    location TEXT NOT NULL,
    location_id TEXT,
    city TEXT,
    country_code TEXT,
    current_stock INTEGER NOT NULL CHECK (current_stock >= 0),
    reorder_point INTEGER NOT NULL CHECK (reorder_point >= 0),
    safety_stock INTEGER NOT NULL CHECK (safety_stock >= 0),
    optimal_stock INTEGER NOT NULL CHECK (optimal_stock >= safety_stock),
    min_order_qty INTEGER,
    lead_time_days INTEGER,
    pending_order_qty INTEGER,
    stockout_days_history INTEGER,
    total_sales_history INTEGER,
    latent_demand_signal_history REAL,
    inventory_status TEXT,
    avg_daily_demand_30d REAL NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL,
    PRIMARY KEY (part_id, location),
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    part_id INTEGER NOT NULL,
    location TEXT NOT NULL DEFAULT 'My Store',
    location_id TEXT,
    current_stock INTEGER NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    reorder_point INTEGER NOT NULL DEFAULT 0 CHECK (reorder_point >= 0),
    safety_stock INTEGER NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
    optimal_stock INTEGER NOT NULL DEFAULT 1 CHECK (optimal_stock >= safety_stock),
    min_order_qty INTEGER,
    lead_time_days INTEGER,
    pending_order_qty INTEGER NOT NULL DEFAULT 0 CHECK (pending_order_qty >= 0),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, part_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_stock_user ON user_stock(user_id);
CREATE INDEX IF NOT EXISTS idx_user_stock_part ON user_stock(part_id);

CREATE TABLE IF NOT EXISTS inventory_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_timestamp TEXT,
    snapshot_timestamp_utc TEXT,
    snapshot_date TEXT,
    location_id TEXT,
    city TEXT,
    country_code TEXT,
    sku TEXT,
    part_name TEXT,
    category TEXT,
    supplier_id TEXT,
    current_stock INTEGER,
    reorder_point INTEGER,
    safety_stock INTEGER,
    optimal_stock INTEGER,
    min_order_qty INTEGER,
    lead_time_days INTEGER,
    pending_order_qty INTEGER,
    stockout_days_history INTEGER,
    total_sales_history INTEGER,
    latent_demand_signal_history REAL,
    inventory_status TEXT
);

CREATE TABLE IF NOT EXISTS demand_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL,
    sale_date TEXT NOT NULL,
    location TEXT NOT NULL,
    location_type TEXT NOT NULL,
    sales_quantity INTEGER NOT NULL CHECK (sales_quantity >= 0),
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sales_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    timestamp_utc TEXT,
    date TEXT NOT NULL,
    sku TEXT NOT NULL,
    part_id INTEGER,
    part_name TEXT,
    category TEXT,
    seasonality_profile TEXT,
    location_id TEXT NOT NULL,
    city TEXT,
    country TEXT,
    country_code TEXT,
    climate_zone TEXT,
    quantity_sold INTEGER NOT NULL CHECK (quantity_sold >= 0),
    latent_demand_signal REAL,
    unit_price_eur REAL,
    revenue_eur REAL,
    stock_on_hand_end INTEGER,
    stockout_flag INTEGER,
    day_of_week INTEGER,
    day_name TEXT,
    day_of_month INTEGER,
    week_of_year INTEGER,
    month INTEGER,
    quarter INTEGER,
    year INTEGER,
    season TEXT,
    is_weekend INTEGER,
    temperature_c REAL,
    temp_change_1d_c REAL,
    temp_change_3d_c REAL,
    abs_temp_change_3d_c REAL,
    rain_mm REAL,
    snow_cm REAL,
    cold_snap_flag INTEGER,
    heatwave_flag INTEGER,
    weather_spike_flag INTEGER,
    temperature_drop_flag INTEGER,
    temperature_rise_flag INTEGER,
    is_payday INTEGER,
    is_payday_window INTEGER,
    is_holiday INTEGER,
    is_school_holiday INTEGER,
    event_name TEXT,
    event_type TEXT,
    affected_categories TEXT,
    event_multiplier REAL,
    promotion_flag INTEGER,
    service_campaign_flag INTEGER,
    fuel_price_eur_l REAL,
    mobility_index REAL,
    mean_demand_before_stock REAL,
    weather_spike_applied REAL,
    salary_spike_applied REAL,
    calendar_spike_applied REAL,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS order_sales_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_client_id TEXT NOT NULL,
    order_client_line_id INTEGER NOT NULL UNIQUE,
    user_id INTEGER,
    part_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    part_name TEXT NOT NULL,
    category TEXT,
    location TEXT NOT NULL,
    quantity_sold INTEGER NOT NULL CHECK (quantity_sold >= 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    revenue_eur REAL NOT NULL CHECK (revenue_eur >= 0),
    sold_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (order_client_id) REFERENCES order_clients(id) ON DELETE CASCADE,
    FOREIGN KEY (order_client_line_id) REFERENCES order_client_lines(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS weather_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    timestamp_utc TEXT,
    date TEXT,
    location_id TEXT,
    city TEXT,
    country_code TEXT,
    climate_zone TEXT,
    temperature_c REAL,
    temp_change_1d_c REAL,
    temp_change_3d_c REAL,
    abs_temp_change_3d_c REAL,
    rain_mm REAL,
    snow_cm REAL,
    cold_snap_flag INTEGER,
    heatwave_flag INTEGER,
    weather_spike_flag INTEGER,
    temperature_drop_flag INTEGER,
    temperature_rise_flag INTEGER
);

CREATE TABLE IF NOT EXISTS calendar_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    timestamp_utc TEXT,
    date TEXT,
    location_id TEXT,
    city TEXT,
    country_code TEXT,
    is_payday INTEGER,
    is_payday_window INTEGER,
    is_holiday INTEGER,
    is_school_holiday INTEGER,
    event_name TEXT,
    event_type TEXT,
    affected_categories TEXT,
    event_multiplier REAL,
    promotion_flag INTEGER,
    service_campaign_flag INTEGER
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    timestamp_utc TEXT,
    date TEXT,
    location_id TEXT,
    city TEXT,
    country_code TEXT,
    is_payday INTEGER,
    is_payday_window INTEGER,
    is_holiday INTEGER,
    is_school_holiday INTEGER,
    event_name TEXT,
    event_type TEXT,
    affected_categories TEXT,
    event_multiplier REAL,
    promotion_flag INTEGER,
    service_campaign_flag INTEGER
);

CREATE TABLE IF NOT EXISTS dataset_dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT,
    column_name TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS order_clients (
    id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    user_id INTEGER,
    location TEXT NOT NULL,
    requested_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending','Approved','Denied','Scheduled','Delivered')),
    fulfillment_status TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK (fulfillment_status IN ('unreviewed','ready','partial','backorder','fulfilled','denied')),
    scheduled_for TEXT,
    stock_applied INTEGER NOT NULL DEFAULT 0 CHECK (stock_applied IN (0, 1)),
    shortage_quantity INTEGER NOT NULL DEFAULT 0 CHECK (shortage_quantity >= 0),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS order_client_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    part_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    part_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    allocated_quantity INTEGER NOT NULL DEFAULT 0 CHECK (allocated_quantity >= 0),
    shortage_quantity INTEGER NOT NULL DEFAULT 0 CHECK (shortage_quantity >= 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES order_clients(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS order_suppliers (
    id TEXT PRIMARY KEY,
    supplier_id TEXT,
    supplier_name TEXT NOT NULL,
    user_id INTEGER,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending','Approved','Delivered','Delayed','Refused','Received')),
    estimated_arrival TEXT NOT NULL,
    postponed_until TEXT,
    received_at TEXT,
    source_client_order_id TEXT,
    stock_applied INTEGER NOT NULL DEFAULT 0 CHECK (stock_applied IN (0, 1)),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS order_supplier_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    part_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    part_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    received_quantity INTEGER NOT NULL DEFAULT 0 CHECK (received_quantity >= 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES order_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS order_notification_stream (
    user_id INTEGER PRIMARY KEY,
    last_generated_at TEXT NOT NULL,
    next_kind TEXT NOT NULL DEFAULT 'client'
        CHECK (next_kind IN ('client','supplier')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL,
    forecast_date TEXT,
    horizon_days INTEGER NOT NULL CHECK (horizon_days > 0),
    predicted_demand INTEGER NOT NULL CHECK (predicted_demand >= 0),
    confidence_score REAL NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    generated_at TEXT NOT NULL,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('order', 'reduce', 'transfer')),
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    source_location TEXT,
    target_location TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS forecast_actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id INTEGER NOT NULL,
    actual_demand INTEGER NOT NULL CHECK (actual_demand >= 0),
    measured_at TEXT NOT NULL,
    FOREIGN KEY (forecast_id) REFERENCES forecasts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_parts_sku ON parts(sku);
CREATE INDEX IF NOT EXISTS idx_stock_location_id ON stock(location_id);
CREATE INDEX IF NOT EXISTS idx_sales_history_sku_date ON sales_history(sku, date);
CREATE INDEX IF NOT EXISTS idx_sales_history_location_date ON sales_history(location_id, date);
CREATE INDEX IF NOT EXISTS idx_demand_history_part_date ON demand_history(part_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_order_sales_events_user_sold_at ON order_sales_events(user_id, sold_at);
CREATE INDEX IF NOT EXISTS idx_order_sales_events_category_sold_at ON order_sales_events(category, sold_at);
CREATE INDEX IF NOT EXISTS idx_order_clients_status ON order_clients(status);
CREATE INDEX IF NOT EXISTS idx_order_clients_location ON order_clients(location);
CREATE INDEX IF NOT EXISTS idx_order_client_lines_order ON order_client_lines(order_id);
CREATE INDEX IF NOT EXISTS idx_order_suppliers_status ON order_suppliers(status);
CREATE INDEX IF NOT EXISTS idx_order_suppliers_supplier ON order_suppliers(supplier_id);
CREATE INDEX IF NOT EXISTS idx_order_supplier_lines_order ON order_supplier_lines(order_id);
