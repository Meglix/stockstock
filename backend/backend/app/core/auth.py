from datetime import datetime, timedelta, timezone
import logging
import os

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_connection
from app.core.user_scope import get_user_location_scope_records


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

logger = logging.getLogger(__name__)
security = HTTPBearer()


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode(), salt).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def create_access_token(user_id: int, username: str, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expires_at,
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.warning("Generated JWT token for user_id=%s username=%s token=%s", user_id, username, token)
    return token


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from error


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT u.id, u.username, u.full_name, u.company, u.email, u.location_id, u.is_active, r.role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user = dict(row)
    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    role_name = user.get("role_name")
    if role_name == "user":
        connection = get_connection()
        location_scope = get_user_location_scope_records(connection, int(user["id"]))
        user["user_location_ids"] = [scope["location_id"] for scope in location_scope]
        user["user_locations"] = [scope["location"] for scope in location_scope]
        connection.close()
    else:
        user["user_location_ids"] = []
        user["user_locations"] = []

    return user


def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role_name"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def require_authenticated_user(current_user: dict = Depends(get_current_user)):
    return current_user


def require_user_or_supplier(current_user: dict = Depends(get_current_user)):
    return require_authenticated_user(current_user)
