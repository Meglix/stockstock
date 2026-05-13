from fastapi import HTTPException


def role_name(current_user: dict) -> str:
    return current_user.get("role_name", current_user.get("role", "user"))


def is_admin(current_user: dict) -> bool:
    return role_name(current_user) == "admin"


def user_order_locations(current_user: dict) -> set[str]:
    location_ids = current_user.get("user_location_ids") or []
    locations = current_user.get("user_locations") or []
    return {str(value) for value in [*location_ids, *locations] if value}


def require_order_location_access(current_user: dict, location: str | None) -> None:
    if is_admin(current_user):
        return

    allowed_locations = user_order_locations(current_user)
    if not allowed_locations:
        raise HTTPException(status_code=403, detail="No order locations assigned to user")
    if location not in allowed_locations:
        raise HTTPException(status_code=403, detail="Order location is outside user scope")


def require_payload_location_for_scoped_user(current_user: dict, location: str | None) -> None:
    if is_admin(current_user):
        return
    if not user_order_locations(current_user):
        return
    if not location:
        raise HTTPException(status_code=400, detail="location is required for scoped users")
    require_order_location_access(current_user, location)


def require_order_record_access(current_user: dict, order: dict) -> None:
    if is_admin(current_user):
        return
    user_id = order["user_id"] if "user_id" in order.keys() else None
    location = order["location"] if "location" in order.keys() else None
    if user_id == current_user.get("id"):
        return
    require_order_location_access(current_user, location)


def scoped_location_clause(current_user: dict, column: str = "location") -> tuple[str, list[str]]:
    if is_admin(current_user):
        return "", []

    allowed_locations = sorted(user_order_locations(current_user))
    if not allowed_locations:
        return " AND 1 = 0", []

    placeholders = ", ".join(["?"] * len(allowed_locations))
    return f" AND {column} IN ({placeholders})", allowed_locations
