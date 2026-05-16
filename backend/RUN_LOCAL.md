# Run Locally

This project is split into two independent folders:

- Backend app: `backend\backend`
- Frontend app: `frontend`

The frontend talks to the backend through relative `/api/...` calls. `frontend\next.config.mjs` rewrites those calls to `http://localhost:8000` by default, so the frontend should not import backend files or use absolute filesystem paths.

## 1. Start Backend

Open PowerShell:

```powershell
cd backend\backend
..\venv\Scripts\Activate.ps1
py -m uvicorn app.main:app --reload
```

Backend URLs:

- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The active database is:

```text
backend\backend\database\stock_optimizer.db
```

Do not use older copies from AppData or other folders when demonstrating live DB changes.

## 2. Start Frontend

Open a second PowerShell:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

- http://localhost:3000

If the backend is not on port `8000`, start the frontend with a different backend target:

```powershell
$env:BACKEND_URL="http://localhost:8001"
npm run dev
```

## 3. Quick Verification

Backend:

```powershell
cd backend\backend
py -B -c "import ast, pathlib; ast.parse(pathlib.Path('app/main.py').read_text()); print('backend syntax ok')"
```

Frontend:

```powershell
cd frontend
npm exec tsc -- --noEmit
```

Browser flow:

1. Open http://localhost:3000
2. Register or log in.
3. Check Dashboard, Parts, Stock, and Orders.
4. In Orders, incoming client/supplier notifications are generated through backend APIs, not hardcoded in the frontend.

## 4. Data Persistence

The backend does not reset the DB on every start.

- `AUTO_BOOTSTRAP_DB=true` applies the schema every start and seeds only if the database is missing or incomplete.
- `RESET_DB_ON_START=false` preserves users, stock edits, and workflow orders.
- `REFRESH_CSV_ON_START=false` avoids reloading the large CSV-backed history tables on every start.

If you changed CSV seed data and want a non-destructive refresh on startup:

```powershell
$env:REFRESH_CSV_ON_START="true"
py -m uvicorn app.main:app --reload
```

Only reset when you intentionally want a clean demo database:

```powershell
cd backend\backend
py scripts\init_db.py --reset
py scripts\seed_data.py --reset
```
