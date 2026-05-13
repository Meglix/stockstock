from __future__ import annotations


def target_stock(optimal_stock: int | float | None, reorder_point: int | float | None = 0) -> int:
    return max(int(optimal_stock or 0), int(reorder_point or 0), 1)


def stock_health(current_stock: int | float | None, optimal_stock: int | float | None, reorder_point: int | float | None = 0) -> str:
    current = int(current_stock or 0)
    target = target_stock(optimal_stock, reorder_point)
    coverage = current / target

    if current <= 0 or coverage < 0.35:
        return "Critical"
    if coverage < 0.6:
        return "Low Stock"
    if coverage < 0.8:
        return "Reorder Soon"
    if coverage >= 1.45:
        return "Overstock"
    return "Healthy"


def catalog_stock_status(current_stock: int | float | None, recommended_stock: int | float | None, availability: str) -> str:
    if availability == "order-only":
        return "Order Only"

    status = stock_health(current_stock, recommended_stock)
    if status in {"Healthy", "Reorder Soon"}:
        return "In Stock"
    return status
