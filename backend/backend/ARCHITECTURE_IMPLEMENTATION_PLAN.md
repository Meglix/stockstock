# Backend Architecture - Maintenance Plan

## Purpose

This plan describes the current backend maintenance approach after cleanup.

Goals:

- keep backend surface aligned with active frontend usage
- avoid dead routes and duplicate routers
- preserve behavior unless change is explicitly requested
- keep docs, tests, and mounted routers in sync

## Current Baseline (Verified)

- FastAPI app with JWT auth and SQLite
- Active domains: auth, parts, stock, orders, dashboard summary, notifications, health
- Orders workflow endpoints are active and tested
- Dashboard KPI values are served inside `/dashboard/summary`
- DB bootstrap and CSV seed are non-destructive by default
- Backend test suite passes

## Active Router Contract

Mounted routers in `app/main.py`:

- `app.infrastructure.routers.auth`
- `app.infrastructure.routers.health`
- `app.inventory.routers.parts`
- `app.inventory.routers.stock`
- `app.inventory.routers.orders`
- `app.analytics.routers.dashboard`
- `app.analytics.routers.notifications`

## Documentation Consistency Rules

When backend modules change:

1. Update `backend/API.md`
2. Update `backend/README.md`
3. Update `backend/ARCHITECTURE.md`
4. Update root docs if cross-project behavior changes:
   - `README.md`
   - `APP_ARCHITECTURE.md`
   - `RUN_LOCAL.md` if run flow changes

## Change Safety Rules

1. Do not remove endpoints unless they are not used by active frontend flow.
2. If removing routes, remove router import/registration in `app/main.py` in the same change.
3. Keep schema/history tables when useful for seed continuity, even if no endpoint is mounted.
4. Preserve request and response contracts for active frontend endpoints.
5. Validate with tests after cleanup/refactor changes.

## Validation Checklist

Run after backend changes:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q
```

Minimum checks:

- app imports and starts
- auth tests green
- parts tests green
- stock tests green
- no missing router imports in `app/main.py`
- docs do not mention removed active endpoints

## Near-Term Priorities

1. Keep docs synchronized with mounted routes.
2. Gradually reduce warning noise (deprecated datetime usage, pydantic alias warnings).
3. Add lightweight API smoke checks for active endpoints.
4. Maintain clear separation between active API surface and future analytical scope.

## Definition of Done For Maintenance Changes

- no broken imports or missing routers
- tests pass
- active docs match active backend behavior
- no frontend-impacting contract regressions
