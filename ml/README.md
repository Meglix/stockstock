# Stock Optimizer Automotive - ML Module

Modul ML pentru proiectul **Stock Optimizer Automotive**.

Scopul modulului este sa produca predictii de cerere, segmentare SKU-location, recomandari de reaprovizionare si alerte operationale care pot fi consumate de backend si frontend. Repo-ul contine date sintetice, pipeline de training, modele salvate, output-uri CSV/JSON si un API FastAPI minimal pentru integrare.


Acest repository acopera partea de **machine learning / data science**:

- generare si pregatire dataset sintetic;
- feature engineering pentru vanzari, calendar, vreme, stoc si furnizori;
- model de demand forecasting pe SKU si locatie;
- segmentare SKU-location cu KMeans;
- recomandari de tip `order`, `reduce`, `monitor`;
- alerte de risc stockout/overstock;
- decision layer pentru dashboard: risc, explicatii, scenarii, monitoring;
- endpoint-uri API/CSV-uri pe care backend-ul si frontend-ul le pot consuma.


## Structura proiectului

```text
stock_optimizer_ml_eu/
|-- app/                         # API FastAPI pentru integrare
|-- ml/                          # generator date, features, training, forecast, clustering, recomandari
|-- scripts/                     # scripturi pentru pipeline
|-- data/
|   |-- raw/                     # date sintetice de intrare
|   |   |-- sales_history.csv
|   |   |-- by_location/sales_*.csv
|   |   |-- eu_locations.csv
|   |   |-- parts_master.csv
|   |   |-- suppliers.csv
|   |   |-- weather_daily.csv
|   |   |-- weather_forecast_open_meteo.csv     # optional, forecast meteo live
|   |   |-- calendar_daily.csv
|   |   |-- calendar_events.csv
|   |   |-- inventory_snapshot.csv
|   |   |-- dataset_dictionary.csv
|   |   `-- dataset_summary.json
|   `-- processed/               # output-uri ML
|       |-- forecast_30d.csv
|       |-- recommendations.csv
|       |-- alerts.csv
|       |-- segments_kmeans.csv
|       |-- model_metrics.json
|       |-- forecast_16d.csv                    # optional, demo forecast cu Open-Meteo
|       |-- business_alert_backtest_21d.json
|       `-- decision_layer/
|-- models/                      # modele joblib + metadata
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- Makefile
|-- MODEL_CARD.md
|-- ML_CONTRACT.md
|-- DEMO_SCENARIO.md
`-- PRESENTATION_CHART_GUIDE.md
```

## Dataset

Datasetul curent este sintetic si este descris in `data/raw/dataset_summary.json`.

```text
Randuri vanzari: 157,896
Perioada istoric vanzari: 2024-01-01 - 2025-12-31
Locatii UE: 12
SKU-uri: 18
Perechi SKU-location: 216
Forecast generat: 2026-01-01 - 2026-01-30
```

Locatii incluse:

```text
Helsinki, Stockholm, Tallinn, Copenhagen, Amsterdam, Berlin,
Warsaw, Prague, Bucharest, Milan, Madrid, Paris
```

Exemple de SKU-uri:

- lichid parbriz iarna/vara;
- stergatoare;
- baterie;
- antigel/coolant;
- filtre;
- ulei;
- placute frana;
- anvelope iarna/vara;
- AdBlue;
- covorase cauciuc.

Datele includ:

- timestamp local si UTC;
- temperatura, ploaie, zapada, cold snap, heatwave, weather spike;
- variatie temperatura pe 1 zi si 3 zile;
- payday, holiday, school holiday, promotii si campanii service;
- fuel price si mobility index;
- stoc curent, lead time, reorder point, safety stock;
- furnizori si reliability score.

### Open-Meteo live weather forecast

Proiectul poate consuma forecast meteo real de la **Open-Meteo** pentru urmatoarele 1-16 zile. Pentru uz non-comercial Open-Meteo nu necesita API key.

Comanda:

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe scripts\fetch_open_meteo_weather.py --forecast-days 16
```

Output:

```text
data/raw/weather_forecast_open_meteo.csv
data/raw/weather_forecast_open_meteo_metadata.json
```

Fisierul contine aceleasi feature-uri meteo folosite de model:

- `temperature_c`
- `rain_mm`
- `snow_cm`
- `temp_change_1d_c`
- `temp_change_3d_c`
- `cold_snap_flag`
- `heatwave_flag`
- `weather_spike_flag`
- `temperature_drop_flag`
- `temperature_rise_flag`
- `weather_source`

Cand `weather_forecast_open_meteo.csv` exista si datele se suprapun cu perioada de forecast, `run_forecast` foloseste automat Open-Meteo in locul vremii sintetice. Pentru restul zilelor ramane fallback-ul sintetic.

Exemplu demo cu perioada live:

```powershell
.\.venv\Scripts\python.exe scripts\run_forecast.py --horizon 16 --start-date 2026-05-13
```

Outputul rezultat este:

```text
data/processed/forecast_16d.csv
data/processed/forecast_16d.json
```

### Sezonalitate si semnale business

Generatorul de date include reguli business explicite:

- `PEU-WF-WINTER-5L` creste in sezonul rece, mai devreme in tarile nordice.
- Baterii, stergatoare si antigel cresc la frig, zapada sau scaderi bruste de temperatura.
- AC/cooling si filtrele de habitaclu cresc in perioade calde.
- Produsele de mentenanta pot avea uplift in jurul zilelor de salariu.
- Campaniile service si evenimentele calendaristice influenteaza cererea.

Fisiere utile pentru verificare:

- `data/processed/seasonality_checks.csv`
- `data/processed/exogenous_spike_checks.csv`
- `data/processed/sales_intelligence/`

## Modele implementate

### 1. Demand forecasting

Model principal:

```text
ExtraTreesRegressor_global_local_two_stage_guard
```

Target:

```text
quantity_sold
```

Modelul este antrenat global pe toate perechile SKU-location si foloseste:

- SKU, locatie, tara, categorie, climate zone;
- calendar: zi, luna, saptamana, sezon, weekend, payday, holiday, campanie;
- vreme: temperatura, ploaie, zapada, cold snap, heatwave, weather spike;
- lag-uri: `lag_1`, `lag_7`, `lag_14`, `lag_28`;
- rolling windows: `rolling_mean_7`, `rolling_mean_14`, `rolling_mean_28`, `rolling_std_14`, `rolling_max_28`, `rolling_min_28`.

Forecastul final include si campuri pentru calibrare si model two-stage:

- `raw_predicted_quantity`
- `local_guard_prediction`
- `sale_probability`
- `conditional_quantity_if_sale`
- `two_stage_predicted_quantity`
- `prediction_scope`
- `local_calibration_weight`
- `local_calibration_scale`

Output principal:

```text
data/processed/forecast_30d.csv
```

### Metrici forecast curente

Metricile sunt citite din `data/processed/model_metrics.json`.

Validare daily:

```text
Validation period: 2025-11-17 - 2025-12-31

Final forecast:
MAE: 0.5160
RMSE: 0.8222
MAPE: 7.1335%
WAPE: 5.8304%
R2: 0.9872

Baseline rolling_mean_28:
MAE: 1.0389
RMSE: 1.6360
MAPE: 12.9452%
WAPE: 11.7392%
R2: 0.9494
```

Metrici agregate pe orizont operational de 21 zile:

```text
overall_21d WAPE: 1.8109%
high_volume_21d WAPE: 1.8109%
weather_sensitive_category_21d WAPE: 2.2673%
```

Observatie: datele sunt sintetice si high-signal, deci metricile sunt potrivite pentru demo/proiect, nu pentru promisiuni de productie pe date reale.

### 2. Segmentare SKU-location

Model:

```text
KMeans_SKU_location_segmentation
```

Unitate analizata:

```text
SKU + location_id
```

Output:

```text
data/processed/segments_kmeans.csv
```

Segmente curente:

```text
fast_moving_stable: 119
salary_event_sensitive: 60
summer_heat_sensitive: 12
promotion_travel_sensitive: 12
winter_weather_sensitive: 11
slow_moving_intermittent: 2
```

Features folosite:

- average demand;
- standard deviation;
- coefficient of variation;
- zero-sales share;
- stockout rate;
- winter/summer ratio;
- payday uplift;
- weather spike/cold snap/heatwave uplift;
- promotion/travel uplift;
- mean stock.

## Recomandari si alerte

Output principal:

```text
data/processed/recommendations.csv
```

Distributie recomandari curente:

```text
order: 20
monitor: 172
reduce: 24
```

Campuri utile pentru backend/frontend:

- `sku`
- `part_name`
- `category`
- `location_id`
- `city`
- `current_stock`
- `safety_stock`
- `optimal_stock`
- `lead_time_days`
- `supplier_id`
- `supplier_name`
- `forecast_demand_7d`
- `forecast_demand_14d`
- `forecast_demand_30d`
- `days_until_stockout`
- `coverage_ratio_horizon`
- `recommended_action`
- `recommended_qty`
- `priority`
- `explanation`

Output alerte:

```text
data/processed/alerts.csv
```

Tipuri de alerte generate:

- `stockout_risk`
- `overstock`

In decision layer, alertele pot include si semnale de tip `weather_demand_spike`, folosite pentru ranking de risc si explicabilitate.

## Decision layer

Pentru dashboard si demo, pipeline-ul genereaza un strat suplimentar in:

```text
data/processed/decision_layer/
```

Fisiere principale:

- `dealer_alert_center.csv` - alerte actionabile pentru dealer;
- `stock_risk_reorder_engine.csv` - risc stockout, acoperire, lead time, cantitate recomandata;
- `product_sensitivity_profiles.csv` - profil SKU-location;
- `forecast_scenarios_21d.csv` - scenarii pesimist/expected/optimist/weather/payday;
- `dealer_risk_map.csv` - risc agregat pe locatie;
- `model_explainability.csv` - explicatii pentru alerte;
- `model_monitoring_summary.json` - sumar monitoring model;
- `data_drift_report.csv` - raport drift;
- `data_integrations_catalog.csv` - catalog integrari disponibile/simulate/neconectate.

Row counts curente:

```text
dealer_alerts: 2
stock_risk_rows: 216
sensitivity_profiles: 216
scenario_rows: 216
risk_map_locations: 12
explainability_rows: 2
integrations: 10
```

Backtestul de alerte pe 21 zile este tratat ca proxy de ranking/risc, nu ca promisiune exacta de vanzari:

```text
evaluation_type: risk_ranking_proxy
windows_evaluated: 648
positive_event_windows: 25
alert_precision_percent: 0.62
alert_recall_percent: 4.0
stockout_windows_actual: 0
stockout_windows_flagged: 0
```

Interpretare: precision/recall mici aici indica faptul ca euristica de alertare este zgomotoasa pe ferestrele sintetice de holdout. Pentru prezentare, accentul trebuie pus pe forecast, recomandari si explicabilitate, nu pe backtestul de alerte ca metrica principala.

## Contract ML pentru backend/frontend

Backend-ul poate consuma direct CSV/JSON din `data/processed` sau poate apela API-ul FastAPI.

Contractul detaliat este in `ML_CONTRACT.md`.

### Input-uri asteptate de ML

Pentru o varianta reala, backend-ul ar trebui sa livreze:

- istoric vanzari pe zi, SKU si locatie;
- catalog produse;
- locatii/dealeri;
- snapshot stoc curent;
- lead time si supplier;
- evenimente calendaristice/promotii;
- date meteo sau forecast meteo.

### Output-uri livrate de ML

ML-ul livreaza:

- forecast pe urmatoarele 30 zile;
- cerere estimata pe 7/14/30 zile;
- actiune recomandata: `order`, `reduce`, `monitor`;
- cantitate recomandata;
- prioritate;
- risc stockout/overstock;
- explicatie text pentru decizie;
- segment SKU-location;
- date pentru grafice si dashboard.

## Rulare locala

### Windows PowerShell

```powershell
cd stock_optimizer_ml_eu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

### Bash/Linux/macOS

```bash
cd stock_optimizer_ml_eu
python -m pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Rulare cu Docker

```bash
cd stock_optimizer_ml_eu
docker compose up --build
```

API-ul va fi disponibil la:

```text
http://localhost:8000
```

## Pipeline complet

Datele si modelele sunt deja generate in repo, dar pipeline-ul poate fi reconstruit.

Cu Make:

```bash
make build-all
```

Pas cu pas:

```bash
make data
make train
make cluster
make forecast
make recommend
make decision
```

Pe Windows, se pot rula direct scripturile cu Python:

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe scripts\build_all.py
```

Pentru weather live + forecast demo:

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe scripts\fetch_open_meteo_weather.py --forecast-days 16
.\.venv\Scripts\python.exe scripts\run_forecast.py --horizon 16 --start-date 2026-05-13
```

## Endpoint-uri API

```text
GET  /health
GET  /model/metadata
GET  /data/locations
GET  /data/parts
GET  /data/weather?location_id=FI_HEL&start_date=2025-09-01&end_date=2025-09-30
GET  /data/open-meteo-weather?location_id=FI_HEL
GET  /data/events?location_id=FI_HEL
GET  /forecast/{sku}?location_id=FI_HEL&horizon=30
GET  /forecast?sku=PEU-WF-WINTER-5L&location_id=FI_HEL
GET  /segments?sku=PEU-WF-WINTER-5L
GET  /recommendations?action=order&priority=high
GET  /alerts?priority=medium
GET  /kpis
GET  /decision/alerts
GET  /decision/stock-risk
GET  /decision/sensitivity-profiles
GET  /decision/scenarios
GET  /decision/map
GET  /decision/explainability
GET  /decision/model-monitoring
GET  /decision/integrations
GET  /dashboard/location-risk?location_id=FI_HEL
GET  /dashboard/forecast-weather?sku=PEU-WF-WINTER-5L&location_id=FI_HEL&horizon=16
GET  /dashboard/alerts-orders?location_id=FI_HEL&priority=high
GET  /dashboard/location?location_id=FI_HEL&sku=PEU-WF-WINTER-5L&horizon=16
POST /decision/build
POST /refresh-outputs
POST /retrain
```

Exemplu:

```bash
curl "http://localhost:8000/forecast/PEU-WF-WINTER-5L?location_id=FI_HEL&horizon=30"
```

## Integrare recomandata in aplicatia finala

Pentru MVP, backend-ul poate expune catre frontend urmatoarele ecrane bazate pe output-uri ML:

- dashboard KPI din `/kpis`;
- grafic forecast din `/forecast`;
- tabel recomandari din `/recommendations`;
- alert center din `/alerts` sau `/decision/alerts`;
- pagina produs cu segment din `/segments`;
- pagina locatie/risc din `/decision/map`;
- explicatii decizie din `/decision/explainability`.

Pentru un dashboard full stack, frontend-ul poate consuma direct endpoint-urile agregate:

- `GET /dashboard/location-risk` pentru zona **Location Risk Overview**;
- `GET /dashboard/forecast-weather` pentru zona **Forecast + Weather**;
- `GET /dashboard/alerts-orders` pentru zona **Alerts & Recommended Orders**;
- `GET /dashboard/location` pentru toate cele 3 zone intr-un singur payload.

Exemplu pentru pagina completa pe o locatie:

```text
GET /dashboard/location?location_id=FI_HEL&sku=PEU-WF-WINTER-5L&horizon=16
```

## Limitari

- Datasetul este sintetic si nu reprezinta date reale Peugeot.
- Datele meteo sunt simulate in dataset, nu vin dintr-un API real.
- Forecastul prezice vanzari observate, nu cerere complet neconstransa.
- Output-urile sunt potrivite pentru demo/proiect si integrare MVP.
- Pentru productie ar fi necesare date reale, monitorizare continua, validare cu business-ul si integrare operationala cu sistemele existente.

## Demo rapid

Scenariul detaliat este in `DEMO_SCENARIO.md`.


