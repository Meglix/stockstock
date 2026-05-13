import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.auth import create_access_token, get_current_user, hash_password, verify_password
from app.core.user_scope import get_user_location_scope_records, set_user_location_scope
from app.db import get_connection


router = APIRouter(prefix="/auth", tags=["auth"])


def _validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one number")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Password must contain at least one special character")
    return v


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$', v):
            raise ValueError("Invalid email address")
        return v


class RegisterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    location_id: str = Field(min_length=1, max_length=50)

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$', v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("location_id")
    @classmethod
    def location_id_format(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Location is required")
        return value


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_location_options(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT location_id, city, country, country_code
        FROM eu_locations
        ORDER BY country, city, location_id
        """
    )
    return [
        {
            **dict(row),
            "label": f"{row['city']}, {row['country']}",
        }
        for row in cursor.fetchall()
    ]


def _get_location_option_by_id(connection, location_id: str):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT location_id, city, country, country_code
        FROM eu_locations
        WHERE location_id = ?
        LIMIT 1
        """,
        (location_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row is not None else None


@router.get("/locations")
def available_locations():
    connection = get_connection()
    try:
        return {"locations": _get_location_options(connection)}
    finally:
        connection.close()


@router.post("/register", status_code=201)
def register(payload: RegisterPayload):
    connection = get_connection()
    cursor = connection.cursor()

    email = normalize_email(payload.email)
    # Derive a unique username from the email local part
    username_base = email.split("@")[0][:50]
    username = username_base
    suffix = 1
    while True:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone() is None:
            break
        username = f"{username_base}{suffix}"
        suffix += 1

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone() is not None:
        connection.close()
        raise HTTPException(status_code=409, detail="Email already registered")

    # Public registration is user-only. Admins are provisioned separately.
    role_name = "user"
    cursor.execute("SELECT id FROM roles WHERE role_name = ?", (role_name,))
    role_row = cursor.fetchone()
    if role_row is None:
        cursor.execute(
            "INSERT INTO roles (role_name, description) VALUES (?, ?)",
            (role_name, f"Auto-created role {role_name}"),
        )
        role_id = cursor.lastrowid
    else:
        role_id = role_row["id"]

    location = _get_location_option_by_id(connection, payload.location_id)
    if location is None:
        connection.close()
        raise HTTPException(status_code=422, detail="Location must match an available EU location")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cursor.execute(
        """
        INSERT INTO users (full_name, company, username, email, location_id, password_hash, role_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.full_name.strip(),
            payload.company.strip(),
            username,
            email,
            location["location_id"],
            hash_password(payload.password),
            role_id,
            now,
            now,
        ),
    )
    connection.commit()
    user_id = cursor.lastrowid
    set_user_location_scope(connection, user_id, [location["location_id"]])

    token = create_access_token(user_id=user_id, username=username, role=role_name)
    connection.close()

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": username,
            "full_name": payload.full_name.strip(),
            "company": payload.company.strip(),
            "email": email,
            "role": role_name,
            "location_id": location["location_id"],
            "location": location["city"],
            "city": location["city"],
            "user_location_ids": [location["location_id"]],
            "user_locations": [location["city"]],
            "message": "Account created successfully",
        },
    }


@router.post("/login")
def login(payload: LoginPayload):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT u.id, u.username, u.full_name, u.company, u.password_hash, u.is_active, u.email, u.location_id, r.role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.email = ?
        """,
        (normalize_email(payload.email),),
    )
    row = cursor.fetchone()

    if row is None:
        connection.close()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = dict(row)
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    token = create_access_token(user_id=user["id"], username=user["username"], role=user["role_name"])
    if user["role_name"] == "user":
        scope_payload = get_user_location_scope_records(connection, int(user["id"]))
        user_location_ids = [scope["location_id"] for scope in scope_payload]
        user_locations = [scope["location"] for scope in scope_payload]
    else:
        user_location_ids = []
        user_locations = []

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user.get("full_name"),
            "company": user.get("company"),
            "email": user["email"],
            "location_id": user.get("location_id"),
            "role": user["role_name"],
            "user_location_ids": user_location_ids,
            "user_locations": user_locations,
        },
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "full_name": current_user.get("full_name"),
        "company": current_user.get("company"),
        "email": current_user["email"],
        "location_id": current_user.get("location_id"),
        "role": current_user["role_name"],
        "user_location_ids": current_user.get("user_location_ids", []),
        "user_locations": current_user.get("user_locations", []),
    }
