# ML Contract - Backend si Frontend

Acest document descrie contractul dintre modulul ML si aplicatia finala **Stock Optimizer Automotive**.

ML-ul livreaza forecast, recomandari, alerte si explicatii. Backend-ul poate consuma fie fisierele CSV/JSON din `data/processed`, fie endpoint-urile FastAPI din `app/main.py`.

## Responsabilitati

ML:

- pregateste datele pentru model;
- antreneaza modelele;
- genereaza forecast pe 30 zile;
- genereaza recomandari de stoc;
- genereaza alerte si explicatii;
- livreaza CSV/JSON/API pentru integrare.

Backend:

- expune datele catre frontend;
- gestioneaza useri, roluri, produse, stoc si comenzi;
- valideaza actiunile operationale;
- salveaza deciziile utilizatorilor.

Frontend:

- afiseaza dashboard-ul;
- permite filtrare dupa produs, locatie, categorie si prioritate;
- afiseaza grafice forecast si alerte;
- permite actiuni precum create order, update stock, accept recommendation.

## Input-uri asteptate de ML

Pentru MVP, fisierele sunt deja generate in `data/raw`.

Pentru o integrare reala, backend-ul ar trebui sa trimita sau sa puna la dispozitie:

| Dataset | Chei minime | Scop |
|---|---|---|
| Sales history | `date`, `sku`, `location_id`, `quantity_sold` | Istoric cerere |
| Parts master | `sku`, `part_name`, `category`, `unit_price_eur` | Catalog produse |
| Locations | `location_id`, `city`, `country_code`, `climate_zone` | Context dealer |
| Inventory snapshot | `sku`, `location_id`, `current_stock_units`, `lead_time_days` | Decizie de stoc |
| Suppliers | `supplier_id`, `supplier_name`, `reliability_score` | Alegere furnizor |
| Calendar/events | `date`, `event_type`, `promotion_flag` | Uplift calendar |
| Weather | `date`, `location_id`, `temperature_c`, `snow_cm`, `rain_mm` | Driver extern |

## Output-uri ML

### Forecast

Fisier:

```text
data/processed/forecast_30d.csv
```

Endpoint:

```text
GET /forecast
GET /forecast/{sku}?location_id=FI_HEL&horizon=30
```

Campuri principale:

| Coloana | Tip | Descriere |
|---|---|---|
| `forecast_date` | date | Ziua pentru care se face predictia |
| `horizon_day` | int | Ziua din orizontul de forecast |
| `sku` | string | Cod produs |
| `part_name` | string | Nume produs |
| `location_id` | string | Cod locatie |
| `city` | string | Oras dealer |
| `predicted_quantity` | float | Cerere prezisa |
| `predicted_revenue_eur` | float | Venit estimat |
| `temperature_c` | float | Temperatura folosita ca feature |
| `cold_snap_flag` | int | Indicator frig |
| `heatwave_flag` | int | Indicator canicula |
| `segment_name` | string | Segment operational |

Exemplu de consum:

```json
{
  "sku": "PEU-WF-WINTER-5L",
  "location_id": "FI_HEL",
  "forecast_date": "2026-01-01",
  "horizon_day": 1,
  "predicted_quantity": 46.4303,
  "city": "Helsinki",
  "segment_name": "promotion_travel_sensitive"
}
```

### Recommendations

Fisier:

```text
data/processed/recommendations.csv
```

Endpoint:

```text
GET /recommendations
GET /recommendations?action=order&priority=high
```

Campuri principale:

| Coloana | Tip | Descriere |
|---|---|---|
| `sku` | string | Cod produs |
| `location_id` | string | Cod locatie |
| `current_stock` | int | Stoc curent |
| `safety_stock` | int | Stoc de siguranta |
| `optimal_stock` | int | Stoc tinta |
| `lead_time_days` | int | Lead time furnizor |
| `forecast_demand_7d` | float | Cerere estimata 7 zile |
| `forecast_demand_14d` | float | Cerere estimata 14 zile |
| `forecast_demand_30d` | float | Cerere estimata 30 zile |
| `days_until_stockout` | float | Zile pana la epuizare stoc |
| `recommended_action` | string | `order`, `reduce`, `monitor` |
| `recommended_qty` | int | Cantitate recomandata |
| `priority` | string | `high`, `medium`, `low` |
| `explanation` | string | Motiv business |

Exemplu:

```json
{
  "sku": "PEU-WF-WINTER-5L",
  "location_id": "FI_HEL",
  "current_stock": 164,
  "forecast_demand_30d": 1317.22,
  "days_until_stockout": 3.74,
  "recommended_action": "order",
  "recommended_qty": 839,
  "priority": "high",
  "explanation": "Risc stockout: 3.7 zile acoperire vs lead time 14 zile."
}
```

### Alerts

Fisier:

```text
data/processed/alerts.csv
```

Endpoint:

```text
GET /alerts
GET /decision/alerts
```

Tipuri de alerte:

- `stockout_risk`;
- `overstock`;
- `weather_demand_spike`.

### Decision layer

Director:

```text
data/processed/decision_layer/
```

Endpoint-uri recomandate:

```text
GET /decision/stock-risk
GET /decision/sensitivity-profiles
GET /decision/scenarios
GET /decision/map
GET /decision/explainability
GET /decision/model-monitoring
GET /decision/integrations
```

## Semnificatia campurilor cheie

`recommended_action`:

- `order`: exista risc de stockout sau stoc insuficient pentru lead time + safety stock;
- `reduce`: exista risc de overstock;
- `monitor`: stocul este acceptabil pentru orizontul analizat.

`priority`:

- `high`: necesita actiune rapida;
- `medium`: necesita verificare;
- `low`: monitorizare normala.

`days_until_stockout`:

- estimare simplificata bazata pe stoc curent si cererea medie forecastata;
- nu este promisiune exacta, ci indicator operational.

`prediction_scope`:

- explica daca forecastul final vine din model global, calibrare locala sau model two-stage.

## Contract de calitate

Backend/frontend pot presupune ca output-urile ML respecta aceste reguli:

- `predicted_quantity >= 0`;
- `recommended_qty >= 0`;
- `horizon_day` este intre 1 si 30 pentru `forecast_30d.csv`;
- `recommended_action` este una dintre `order`, `reduce`, `monitor`;
- `priority` este una dintre `high`, `medium`, `low`;
- fiecare rand important are `sku` si `location_id`.

Regulile sunt validate de testele smoke din `tests/test_smoke_outputs.py`.
