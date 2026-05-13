# Stock Optimizer Automotive

## Description
Local full-stack demo for automotive parts inventory, stock management, supplier replenishment, client orders, notifications, and dashboard analytics.

The current backend runs from SQLite plus CSV seed data. The `ml/` folder is optional and is not required by the active local app.

## Project Structure

- **backend/** -> FastAPI backend organized by business domains (inventory, analytics, core)
- **..\frontend-master/** -> separate Next.js frontend app (demo UI, pages/components in `src/`)
- **ml/** -> optional ML workspace (not required for current backend CSV workflow)
- **data/raw/** -> project-level CSV source used by backend seed

## Architecture Docs

- Current full-stack architecture with diagrams and live SQLite schema details: [APP_ARCHITECTURE.md](APP_ARCHITECTURE.md)
- Backend-focused architecture reference: [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md)
- Current active API reference: [backend/API.md](backend/API.md)

---

## Module Organization (Backend)

The backend is organized by **business domains**, making it easy to locate and maintain code:

| Module | Purpose | Contains |
|--------|---------|----------|
| `core/` | Authentication & security | JWT tokens, password hashing, user validation |
| `inventory/` | Inventory management | Parts, catalog, user stock, and order workflows |
| `analytics/` | Analytics & insights | Dashboard summaries, notifications, future forecast/recommendation hooks |
| `infrastructure/` | Core infrastructure | Auth endpoints, health checks |

---

## Responsibilities

### Backend
- Manages the API (FastAPI)
- Manages the database (SQLite)
- Organized by business domain:
  - **Inventory Module** - parts, catalog, user stock, and order workflows
  - **Analytics Module** - dashboard summaries, notifications, and future forecast/recommendation hooks
  - **Core Module** - authentication and authorization
  - **Infrastructure** - health checks, login endpoints
- Exposes RESTful API endpoints

### Machine Learning
- optional workspace for future forecasting/recommendation work
- not required by the current backend runtime
- current analytics and dashboard behavior are backed by SQLite, API services, and CSV-seeded data

### Current Data Mode
- backend works from local CSVs in `data/raw`
- no active runtime dependency on an ML repository checkout

---

## Commands (Simple)

For a complete step-by-step local run guide, see [RUN_LOCAL.md](RUN_LOCAL.md).

### Backend (local)
```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### Initialize or reset DB (only when needed)
```bash
cd backend
python scripts/init_db.py
python scripts/seed_data.py
```

### Run tests
```bash
cd backend
.\venv\Scripts\python.exe -m pytest -q
```

### Frontend (local)
```bash
cd ..\frontend-master
npm install
npm run dev
```

### Frontend production build (optional)
```bash
cd ..\frontend-master
npm run build
npm run start
```

### Docker
```bash
docker compose up --build
```

### Run Full Demo (Backend + Frontend)

Open 2 terminals from project root.

Terminal 1 (backend):

```bash
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Terminal 2 (frontend):

```bash
cd ..\frontend-master
npm install
npm run dev
```

Demo URLs:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

Note: Docker compose currently starts backend only.

After startup:

- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

See [backend/README.md](backend/README.md) for backend details.
See [backend/API.md](backend/API.md) for the current active API reference.

---

## Adding New Features to Backend

The domain-based structure makes it easy to add new modules:

1. **Create a new domain folder** (e.g., `app/pricing/`)
2. **Add routers** in `app/pricing/routers/` for your endpoints
3. **Add schemas** in `app/pricing/schemas/` for request/response models
4. **Import in main.py** to register routes
5. **Import auth** from `app.core.auth` for protected endpoints

Example:
```python
# app/pricing/routers/price_rules.py
from fastapi import APIRouter
from app.core.auth import require_admin

router = APIRouter()

@router.get("/price-rules")
def get_price_rules():
    # Your logic here
    pass

@router.post("/price-rules")
def create_price_rule(_: dict = Depends(require_admin)):
    # Only admins can create
    pass
```

No other files need changes - the new module integrates automatically.

---

