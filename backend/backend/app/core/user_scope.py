from datetime import datetime, timezone


LOCATION_SCOPE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_location_scope (
    user_id INTEGER NOT NULL,
    location_id TEXT NOT NULL,
    location TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, location_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""


def row_value(row, key: str, index: int):
    try:
        return row[key]
    except (IndexError, TypeError):
        return row[index]


def ensure_user_location_scope_table(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'user_location_scope'
        """
    )
    if cursor.fetchone() is None:
        connection.execute(LOCATION_SCOPE_TABLE_SQL)
        connection.commit()
        return

    cursor.execute("PRAGMA table_info(user_location_scope)")
    columns = {row[1] for row in cursor.fetchall()}

    if "location_id" not in columns:
        cursor.execute("ALTER TABLE user_location_scope RENAME TO user_location_scope_old")
        connection.execute(LOCATION_SCOPE_TABLE_SQL)
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_location_scope (
                user_id, location_id, location, created_at
            )
            SELECT
                old.user_id,
                COALESCE(st.location_id, old.location),
                old.location,
                old.created_at
            FROM user_location_scope_old old
            LEFT JOIN stock st ON st.location = old.location
            WHERE COALESCE(st.location_id, old.location) IS NOT NULL
            """
        )
        cursor.execute("DROP TABLE user_location_scope_old")
    elif "location" not in columns:
        cursor.execute("ALTER TABLE user_location_scope ADD COLUMN location TEXT")
        cursor.execute(
            """
            UPDATE user_location_scope
            SET location = COALESCE(
                (SELECT city FROM eu_locations WHERE eu_locations.location_id = user_location_scope.location_id),
                (SELECT stock.location FROM stock WHERE stock.location_id = user_location_scope.location_id LIMIT 1),
                location_id
            )
            WHERE location IS NULL
            """
        )

    connection.commit()


def list_network_location_scopes(connection) -> list[dict]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            COALESCE(location_id, location) AS location_id,
            COALESCE(MAX(city), MAX(location), location_id, location) AS location
        FROM stock
        WHERE COALESCE(location_id, location) IS NOT NULL
        GROUP BY COALESCE(location_id, location)
        ORDER BY location_id
        """
    )
    return [
        {
            "location_id": row_value(row, "location_id", 0),
            "location": row_value(row, "location", 1) or row_value(row, "location_id", 0),
        }
        for row in cursor.fetchall()
        if row_value(row, "location_id", 0)
    ]


def set_user_location_scope(connection, user_id: int, locations: list[str]):
    ensure_user_location_scope_table(connection)
    cursor = connection.cursor()
    cursor.execute("DELETE FROM user_location_scope WHERE user_id = ?", (user_id,))

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    scope_rows = []
    for location in locations:
        cursor.execute(
            """
            SELECT location_id, city AS location
            FROM eu_locations
            WHERE location_id = ? OR city = ?
            LIMIT 1
            """,
            (location, location),
        )
        location_row = cursor.fetchone()
        if location_row is not None:
            scope_rows.append(
                (
                    user_id,
                    row_value(location_row, "location_id", 0),
                    row_value(location_row, "location", 1),
                    now,
                )
            )
            continue

        cursor.execute(
            """
            SELECT
                COALESCE(st.location_id, st.location) AS location_id,
                COALESCE(st.city, st.location, st.location_id) AS location
            FROM stock st
            WHERE st.location_id = ? OR st.location = ?
            ORDER BY st.location_id
            LIMIT 1
            """,
            (location, location),
        )
        stock_row = cursor.fetchone()
        if stock_row is not None:
            scope_rows.append(
                (
                    user_id,
                    row_value(stock_row, "location_id", 0),
                    row_value(stock_row, "location", 1),
                    now,
                )
            )
            continue

        scope_rows.append((user_id, location, location, now))

    cursor.executemany(
        """
        INSERT INTO user_location_scope (user_id, location_id, location, created_at)
        VALUES (?, ?, ?, ?)
        """,
        scope_rows,
    )
    connection.commit()


def get_user_location_scope_records(connection, user_id: int) -> list[dict]:
    ensure_user_location_scope_table(connection)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT location_id, COALESCE(location, location_id) AS location
        FROM user_location_scope
        WHERE user_id = ?
        ORDER BY location_id
        """,
        (user_id,),
    )
    assigned = [
        {
            "location_id": row_value(row, "location_id", 0),
            "location": row_value(row, "location", 1),
        }
        for row in cursor.fetchall()
    ]
    if assigned:
        return assigned

    return []


def get_user_location_scope(connection, user_id: int) -> list[str]:
    return [
        scope["location_id"]
        for scope in get_user_location_scope_records(connection, user_id)
    ]
