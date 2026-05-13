# MODEL_CARD - Stock Optimizer Automotive ML

## Context

Modelul sustine modulul ML pentru **Stock Optimizer Automotive**. Rolul lui este sa estimeze cererea viitoare pe SKU si locatie, sa identifice riscuri de stoc si sa ofere recomandari operationale care pot fi afisate in dashboard sau consumate de backend.

Acest model card descrie partea de ML, nu aplicatia finala completa. Backend-ul si frontend-ul sunt responsabile pentru utilizatori, CRUD, comenzi, UI si fluxuri operationale.

## Date

Datele sunt sintetice si sunt generate prin `ml/data_generator.py`.

Snapshot curent:

```text
Randuri vanzari: 157,896
Perioada istoric vanzari: 2024-01-01 - 2025-12-31
Locatii UE: 12
SKU-uri automotive: 18
Perechi SKU-location: 216
Forecast generat: 2026-01-01 - 2026-01-30
```

Datele includ:

- vanzari zilnice pe SKU si locatie;
- catalog piese auto;
- locatii/dealeri din UE;
- snapshot de inventar;
- furnizori si reliability score;
- vreme simulata;
- evenimente calendaristice, payday, promotii si campanii service;
- fuel price si mobility index.

Datasetul este high-signal pentru demo: sezonalitatea, vremea si efectele de calendar sunt intentionat clare, astfel incat modelul si recomandarile sa fie usor de explicat.

## Model forecasting

Model principal:

```text
ExtraTreesRegressor_global_local_two_stage_guard
```

Target:

```text
quantity_sold
```

Output principal:

```text
data/processed/forecast_30d.csv
```

Features principale:

- categorice: `sku`, `location_id`, `country_code`, `category`, `seasonality_profile`, `climate_zone`, `event_type`, `season`;
- timp: day of week, day of month, week, month, quarter, year, weekend;
- meteo: temperature, temp change, rain, snow, cold snap, heatwave, weather spike;
- calendar: payday window, holiday, school holiday, event multiplier, promotion, service campaign;
- time-series: lag 1/7/14/28 si rolling mean/std/max/min.

Forecastul contine si campuri pentru calibrare si model two-stage:

- `raw_predicted_quantity`;
- `local_guard_prediction`;
- `sale_probability`;
- `conditional_quantity_if_sale`;
- `two_stage_predicted_quantity`;
- `prediction_scope`;
- `local_calibration_weight`;
- `local_calibration_scale`.

## Metrici curente

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

Metrici agregate pe 21 zile:

```text
overall_21d WAPE: 1.8109%
high_volume_21d WAPE: 1.8109%
weather_sensitive_category_21d WAPE: 2.2673%
```

Interpretare:

- WAPE daily este metrica principala pentru forecast.
- WAPE pe 21 zile este mai apropiat de decizia de inventar, pentru ca stocurile se planifica pe orizont de aprovizionare.
- Metricile sunt bune pentru demo pe date sintetice, dar nu trebuie prezentate ca performanta reala pe date Peugeot sau productie.

## Segmentare operationala

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

Segmentarea ajuta la explicarea recomandarilor si poate fi afisata in pagina de detalii produs.

## Recomandari de inventar

Fisier:

```text
ml/recommend.py
```

Output:

```text
data/processed/recommendations.csv
```

Reguli principale:

- `order` daca stocul estimat nu acopera cererea pe lead time + safety stock;
- `reduce` daca stocul este peste optim si cererea estimata nu justifica nivelul curent;
- `monitor` daca situatia este normala;
- alerte separate pentru stockout, overstock si spike-uri meteo.

Distributie curenta:

```text
order: 20
monitor: 172
reduce: 24
```

## Backtest alerte

Fisier:

```text
data/processed/business_alert_backtest_21d.json
```

Acest backtest trebuie interpretat ca **risk ranking proxy**, nu ca promisiune exacta de vanzari sau ca metrica principala a modelului.

Snapshot curent:

```text
windows_evaluated: 648
alert_windows: 162
true_positive_alerts: 1
false_positive_alerts: 161
false_negative_alerts: 24
alert_precision_percent: 0.62
alert_recall_percent: 4.0
stockout_windows_actual: 0
stockout_windows_flagged: 0
```

Pentru prezentare, accentul trebuie pus pe:

- acuratetea forecastului;
- recomandarea de stoc;
- explicatia deciziei;
- integrarea cu dashboard-ul.

## Limitari

- Datele sunt sintetice.
- Datele meteo sunt simulate, nu vin dintr-un API real.
- Modelul prezice vanzari observate, nu cerere complet neconstransa.
- Alert backtest-ul este proxy de ranking/risc.
- Pentru productie ar fi nevoie de date reale, validare business si monitorizare continua.

## Utilizare recomandata in demo

Scenariul principal recomandat este documentat in `DEMO_SCENARIO.md`.

Pe scurt:

1. Arata forecast pentru `PEU-WF-WINTER-5L` in `FI_HEL`.
2. Arata recomandarea de `order` pentru acelasi produs/locatie.
3. Arata risk engine si explicatia deciziei.
4. Explica faptul ca backend/frontend folosesc aceste output-uri pentru dashboard si fluxul de comanda.
