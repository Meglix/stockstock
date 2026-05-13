import logging


def test_login_success(client, caplog):
    payload = {"email": "admin@test.local", "password": "AdminPass123!"}

    with caplog.at_level(logging.WARNING, logger="app.core.auth"):
        response = client.post("/auth/login", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert body["user"]["username"] == "admin"
    assert body["user"]["email"] == "admin@test.local"
    assert "Generated JWT token" in caplog.text
    assert body["access_token"] in caplog.text


def test_login_invalid_password(client):
    payload = {"email": "admin@test.local", "password": "wrong-password"}

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_register_success_creates_user_role(client, caplog):
    payload = {
        "full_name": "Demo User",
        "company": "RRParts",
        "email": "user1@test.local",
        "password": "StrongPass1!",
        "location_id": "RO_BUC",
    }

    with caplog.at_level(logging.WARNING, logger="app.core.auth"):
        response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "user1@test.local"
    assert body["user"]["role"] == "user"
    assert body["user"]["city"] == "Bucharest"
    assert body["user"]["user_locations"] == ["Bucharest"]
    assert "Generated JWT token" in caplog.text
    assert body["access_token"] in caplog.text


def test_register_location_scope_prefers_eu_location_label(client):
    from app.db import get_connection

    connection = get_connection()
    connection.execute(
        """
        INSERT INTO stock (
            part_id, location, location_id, current_stock, reorder_point,
            safety_stock, optimal_stock, avg_daily_demand_30d, last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "RO_BUC", "RO_BUC", 10, 3, 2, 12, 1.0, "2026-05-13"),
    )
    connection.commit()
    connection.close()

    payload = {
        "full_name": "Scoped User",
        "company": "RRParts",
        "email": "scoped-user@test.local",
        "password": "StrongPass1!",
        "location_id": "RO_BUC",
    }

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["location_id"] == "RO_BUC"
    assert body["user"]["user_locations"] == ["Bucharest"]


def test_available_locations_returns_cities(client):
    response = client.get("/auth/locations")

    assert response.status_code == 200
    body = response.json()
    assert body["locations"]
    assert any(location["city"] == "Bucharest" for location in body["locations"])
    assert any(location["location_id"] == "RO_BUC" for location in body["locations"])


def test_register_duplicate_email_fails(client):
    payload = {
        "full_name": "Demo User",
        "company": "RRParts",
        "email": "admin@test.local",
        "password": "StrongPass1!",
        "location_id": "RO_BUC",
    }

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_register_role_injection_is_rejected(client):
    payload = {
        "full_name": "Injected Admin",
        "company": "RRParts",
        "email": "injected@test.local",
        "password": "StrongPass1!",
        "location_id": "RO_BUC",
        "role": "admin",
    }

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_register_weak_password_rejected(client):
    payload = {
        "full_name": "Weak Password",
        "company": "RRParts",
        "email": "weak@test.local",
        "password": "weakpass",
        "location_id": "RO_BUC",
    }

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_me_returns_profile_fields(client):
    login_payload = {"email": "admin@test.local", "password": "AdminPass123!"}
    login_response = client.post("/auth/login", json=login_payload)
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    body = me_response.json()
    assert body["email"] == "admin@test.local"
    assert body["full_name"] == "Admin User"
    assert body["company"] == "RRParts"
    assert body["role"] == "admin"
