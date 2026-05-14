# Demo Scenario - Winter Stock Risk

Acesta este scenariul recomandat pentru prezentarea proiectului. Este scurt, coerent si arata clar ce livreaza partea de ML.

## Poveste

Dealerul din Helsinki intra in sezon rece. Pentru `PEU-WF-WINTER-5L` cererea estimata creste puternic, iar stocul curent nu acopera lead time-ul furnizorului. Modelul recomanda comanda suplimentara si explica riscul.

## Date demo

```text
Produs: PEU-WF-WINTER-5L
Nume: Lichid parbriz iarna -20C 5L
Locatie: FI_HEL
Oras: Helsinki
Orizont forecast: 30 zile
```

## Pasii de prezentare

### 0. Dashboard complet

Endpoint:

```text
GET /dashboard/location?location_id=FI_HEL&sku=PEU-WF-WINTER-5L&horizon=16
```

Ce arati:

- Location Risk Overview;
- Forecast + Weather;
- Alerts & Recommended Orders.

Mesaj:

```text
Frontend-ul poate incarca toate cele 3 zone ale dashboardului dintr-un singur endpoint agregat.
```

### 1. Health check

Endpoint:

```text
GET /health
```

Mesaj:

```text
API-ul vede datele brute, modelele salvate, forecastul, recomandarile si decision layer-ul.
```

### 2. Forecast

Endpoint:

```text
GET /forecast/PEU-WF-WINTER-5L?location_id=FI_HEL&horizon=30
```

Ce arati:

- forecast zilnic;
- zile cu frig/zapada;
- cerere ridicata pentru lichid de parbriz iarna;
- segment operational.

Mesaj:

```text
Modelul foloseste istoric, sezonalitate, vreme si calendar pentru a estima cererea zilnica.
```

### 3. Recommendation

Endpoint:

```text
GET /recommendations?action=order&priority=high
```

Rand demo:

```text
sku: PEU-WF-WINTER-5L
location_id: FI_HEL
current_stock: 164
forecast_demand_30d: 1317.22
days_until_stockout: 3.74
lead_time_days: 14
recommended_action: order
recommended_qty: 839
priority: high
```

Mesaj:

```text
Stocul acopera aproximativ 3.7 zile, dar lead time-ul este 14 zile, deci ML-ul recomanda comanda.
```

### 4. Stock risk engine

Endpoint:

```text
GET /decision/stock-risk?sku=PEU-WF-WINTER-5L&location_id=FI_HEL
```

Ce arati:

- `forecast_21d_units`;
- `projected_stock_after_21d`;
- `coverage_days`;
- `recommended_order_qty`;
- `risk_status`;
- `reorder_message`.

Mesaj:

```text
Decision layer-ul transforma forecastul intr-o decizie operationala: risc, cantitate si mesaj pentru dealer.
```

### 5. Explainability

Endpoint:

```text
GET /decision/explainability
```

Mesaj:

```text
Explicatia nu este doar o predictie: arata driverii principali precum vreme, sezonalitate, baseline si risc de stoc.
```

## Concluzie pentru prezentare

```text
Partea de ML livreaza forecast, recomandare, cantitate, prioritate si explicatie.
Backend-ul transforma aceste output-uri in API-uri si actiuni persistente.
Frontend-ul le afiseaza in dashboard si in fluxul de comanda.
```

## Ce sa nu promiti

- Nu spune ca datele sunt reale Peugeot.
- Nu spune ca alert precision este metrica principala.
- Nu spune ca forecastul este garantie exacta de vanzari.

Formulare recomandata:

```text
Forecastul este folosit ca semnal de decizie si ranking de risc. Pentru productie, modelul trebuie validat pe date reale si monitorizat continuu.
```
