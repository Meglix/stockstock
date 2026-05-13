# Stock Optimizer Automotive - 10 Minute Demo Script

## Presentation Timing

Target format:

- 10 minutes presentation
- 5 minutes Q&A
- English delivery
- Technical audience
- Live demo preferred

## Speaker Roles

| Segment | Speaker | Focus |
|---|---|---|
| Opening and theme | Any team member | Problem, chosen theme, demo promise |
| Backend | Paula | API, auth, SQLite, domain workflows |
| Frontend | Rayan | UI, dashboard, user workflows |
| Machine Learning | Razvan | Forecasting model, alert/recommendation integration |
| Wrap-up | Any team member | Takeaways and Q&A handoff |

## 10 Minute Flow

### 0:00 - 0:45 Opening

Say:

> Our project is Stock Optimizer Automotive, a full-stack application for managing automotive parts inventory, client demand, supplier replenishment, and stock alerts. The main idea is to combine operational workflows with analytics and forecasting so a parts team can decide what needs action quickly.

Show:

- Title slide
- Team slide

### 0:45 - 1:45 Problem And Theme

Say:

> Automotive stock management is difficult because demand changes by location, season, weather, events, and client orders. If a store has too little stock, it cannot fulfill orders. If it has too much stock, money is blocked in inventory. Our app focuses on visibility, fast workflow decisions, and proactive alerts.

Show:

- Problem/theme slide
- Mention technical audience: frontend, backend, data, ML

### 1:45 - 3:00 Architecture

Say:

> The frontend is a Next.js and React application. It calls relative `/api` paths. Next.js rewrites those calls to a FastAPI backend running on port 8000. The backend owns authentication, validation, business rules, and all database writes. The runtime database is SQLite, seeded from CSV files.

Show:

- High-level architecture slide
- Frontend -> rewrite -> backend -> SQLite flow

### 3:00 - 4:00 Data And APIs

Say:

> The dataset includes 12 European locations, 18 catalog parts, 8 suppliers, 216 inventory snapshot rows, more than 157 thousand sales history rows, weather data, calendar events, and per-location sales slices. The backend exposes APIs for auth, catalog, stock, orders, dashboard analytics, and notifications.

Show:

- Dataset/database slide
- API lifecycle slide

### 4:00 - 7:45 Live Demo

#### Step 1: Login

Action:

- Open `http://localhost:3000`.
- Login with a prepared demo account.

Say:

> The login returns a JWT token. The frontend stores it and sends it as a Bearer token on protected requests.

#### Step 2: Dashboard

Action:

- Open dashboard.
- Point to KPIs, monthly demand chart, supplier map, and priority stock.

Say:

> This page is powered by `/dashboard/summary`. The backend aggregates stock, orders, sales events, supplier data, and historical sales fallback data into one dashboard payload.

#### Step 3: Catalog / Parts

Action:

- Open parts/catalog view.
- Show a supplier, category, or product card.

Say:

> The catalog is generated from backend parts and supplier data, enriched with stock availability for the current user.

#### Step 4: Stock Management

Action:

- Open Stock Management.
- Add or update one stock row.

Say:

> The frontend sends a stock payload to `/stock`. The backend validates it with Pydantic and writes it to `user_stock`, which is the current user's store inventory.

#### Step 5: Client Orders

Action:

- Open Orders.
- Show client orders.
- Preview or approve an order.

Say:

> Before approval, the app can preview whether the order can be fulfilled. If stock is available, the backend allocates it. If stock is missing, the workflow becomes a backorder and supplier replenishment can be created.

#### Step 6: Supplier Delivery

Action:

- Switch to supplier orders.
- Receive a delivered supplier order if available.

Say:

> Receiving a supplier delivery increases stock and can make backordered client orders ready to complete.

#### Step 7: Notifications And ML Alerts

Action:

- Open notifications.

Say:

> Notifications combine workflow events, stock alerts, and the forecasting alert integration. The ML model produces forecast and recommendation outputs, and the backend exposes them through the same notification surface.

### 7:45 - 8:45 ML Integration

Say:

> The ML part uses historical sales, inventory, weather, calendar, and location context to forecast demand and generate actionable alerts. The integration point is the backend data layer: forecast, recommendation, and notification rows become available to the dashboard and notification center.

Show:

- ML forecasting integration slide

Important wording:

- If the final ML connection is already merged, mention the exact model name and output path.
- If presenting before final merge, say: "The backend notification surface is prepared and the model outputs are connected through the forecasting and notification tables."

### 8:45 - 9:35 Technical Takeaways

Say:

> The main technical choices are domain-oriented backend modules, typed frontend state, API rewrites for local development, reproducible CSV seed data, and a database model that supports operational workflows and analytics.

Show:

- Key takeaways slide

### 9:35 - 10:00 Q&A Handoff

Say:

> To summarize, Stock Optimizer connects inventory operations, order workflows, analytics, and forecasting alerts in one technical demo. We are ready for questions.

Show:

- Q&A slide

## Live Demo Checklist

Before presenting:

- Backend is running at `http://localhost:8000`.
- Frontend is running at `http://localhost:3000`.
- Swagger docs open in a backup tab: `http://localhost:8000/docs`.
- Demo account credentials are known.
- At least one client order is available for approval/scheduling.
- At least one supplier order is available to receive/postpone/refuse.
- Notification center has workflow or stock alert rows.
- If ML integration is merged, verify generated alerts appear in the notification center.

## Backup Plan

If live demo fails:

1. Show the PowerPoint architecture slides.
2. Open Swagger docs and show the API surface.
3. Show the technical documentation diagrams.
4. Use screenshots or pre-recorded demo clips if available.

## Q&A Cheat Sheet

| Question | Suggested Answer |
|---|---|
| Why is SQLite used? | It keeps the local demo deterministic and easy to run. For production, PostgreSQL would be the natural upgrade. |
| Where are business rules implemented? | In backend domain services, especially inventory and order workflow services. |
| How is the frontend connected? | The frontend calls `/api` routes, and Next.js rewrites them to FastAPI. |
| How are stock changes persisted? | Through FastAPI stock/order endpoints writing to SQLite tables like `user_stock` and order workflow tables. |
| How does ML connect? | The model produces forecasts, recommendations, and alert rows consumed by the backend and shown in dashboard notifications. |
| What is the most important architecture decision? | Keeping business state and workflow transitions in the backend so the UI stays consistent and the database remains the source of truth. |
