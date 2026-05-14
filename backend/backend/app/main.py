from fastapi import FastAPI
from app.db import bootstrap_database_if_needed

# Core routers
from app.infrastructure.routers.auth import router as auth_router
from app.infrastructure.routers.health import router as health_router

# Inventory management routers
from app.inventory.routers.parts import router as parts_router
from app.inventory.routers.stock import router as stock_router
from app.inventory.routers.orders import router as orders_router

# Analytics routers
from app.analytics.routers.dashboard import router as dashboard_router
from app.analytics.routers.notifications import router as notifications_router
from app.analytics.routers.ml import router as ml_router


app = FastAPI(title="Stock Optimizer Backend", version="0.1.0")


@app.on_event("startup")
def startup_tasks():
	bootstrap_database_if_needed()

# Register core infrastructure routers
app.include_router(auth_router)
app.include_router(health_router)

# Register inventory management routers
app.include_router(parts_router)
app.include_router(stock_router)
app.include_router(orders_router)
app.include_router(dashboard_router)
app.include_router(notifications_router)
app.include_router(ml_router)
