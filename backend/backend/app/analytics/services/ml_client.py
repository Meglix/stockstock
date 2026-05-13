from __future__ import annotations

import os
from typing import Any

import httpx


DEFAULT_ML_SERVICE_BASE_URL = os.getenv("ML_SERVICE_BASE_URL", "http://localhost:8001").rstrip("/")
DEFAULT_ML_TIMEOUT_SECONDS = float(os.getenv("ML_SERVICE_TIMEOUT_SECONDS", "5"))


def default_location_id(current_user: dict) -> str | None:
    location_id = current_user.get("location_id")
    if location_id:
        return str(location_id)

    scoped_location_ids = current_user.get("user_location_ids") or []
    if scoped_location_ids:
        return str(scoped_location_ids[0])

    return None


def resolved_location_id(current_user: dict, requested_location: str | None = None) -> str | None:
    if requested_location and requested_location.strip():
        return requested_location.strip()
    return default_location_id(current_user)


def ml_service_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{DEFAULT_ML_SERVICE_BASE_URL}{path}"
    with httpx.Client(timeout=DEFAULT_ML_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def safe_ml_service_get(path: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any] | list[Any], str | None]:
    try:
        return ml_service_get(path, params=params), None
    except (httpx.HTTPError, ValueError) as error:
        return [], str(error)
