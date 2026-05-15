# Presentation Chart Guide

Acest ghid separa ploturile bune de demo de ploturile de diagnostic care nu trebuie aratate in prezentare.

## Model alternativ recomandat

Modelul curent `ExtraTreesRegressor` performeaza bine pe datasetul sintetic. Daca vrei o alternativa utilizabila pe aceleasi date, as testa:

```text
HistGradientBoostingRegressor
```

De ce:

- este in scikit-learn, deci nu adauga dependinte noi;
- merge bine pe date tabulare cu multe semnale non-liniare;
- poate invata interactiuni intre SKU, locatie, vreme, calendar si lag-uri;
- poate fi folosit si in varianta quantile pentru P50/P90, utila la safety stock.

Alte optiuni bune:

- `PoissonRegressor` sau `TweedieRegressor` ca baseline interpretabil pentru count demand;
- un model quantile global pentru intervale de forecast;
- Croston/TSB pentru SKU-uri rare/intermitente, daca vrei o componenta specializata pe slow movers.

Ce nu as alege ca model principal pentru demo:

- Prophet/SARIMAX separat pe fiecare SKU-location, pentru ca ai 216 serii si multi exogeni;
- retele neuronale, pentru ca ar complica proiectul fara castig clar pe datasetul sintetic curent.

## Ploturi bune de aratat

Acestea sunt bune pentru demo, pentru ca sustin povestea business si nu scot in fata slabiciuni inutile.

### Forecast si sezonalitate

```text
data/processed/charts/02_holdout_actual_vs_predicted.png
data/processed/charts/08_forecast_winter_fluid_helsinki.png
data/processed/charts/09_forecast_ac_refill_madrid.png
data/processed/charts/10_forecast_battery_stockholm.png
data/processed/charts/11_winter_fluid_monthly_by_region.png
data/processed/charts/12_ac_refill_monthly_by_region.png
```

### Segmentare

```text
data/processed/charts/05_kmeans_segment_distribution.png
data/processed/charts/06_kmeans_demand_vs_variability.png
data/processed/charts/07_segment_exogenous_profile.png
```

### Sales intelligence

```text
data/processed/sales_intelligence/static_charts/01_product_business_impact.png
data/processed/sales_intelligence/static_charts/02_monthly_seasonality_heatmap.png
data/processed/sales_intelligence/static_charts/05_sales_by_location_heatmap.png
data/processed/sales_intelligence/static_charts/06_weather_trigger_uplift.png
data/processed/sales_intelligence/static_charts/07_forecast_uplift_heatmap.png
data/processed/sales_intelligence/static_charts/08_dealer_alerts_21d.png
```

### Interactive

```text
data/processed/sales_intelligence/interactive_charts/01_product_business_impact.html
data/processed/sales_intelligence/interactive_charts/02_seasonality_vs_weather_sensitivity.html
data/processed/sales_intelligence/interactive_charts/04_sales_heatmap_product_location.html
data/processed/sales_intelligence/interactive_charts/05_forecast_uplift_heatmap.html
data/processed/sales_intelligence/interactive_charts/06_weather_alerts_21d.html
data/processed/sales_intelligence/interactive_charts/07_alerts_explainability_table.html
```

### Decision layer

```text
data/processed/decision_layer/charts/stock_risk_reorder.html
data/processed/decision_layer/charts/dealer_risk_map.html
data/processed/decision_layer/charts/forecast_scenarios.html
data/processed/decision_layer/charts/dealer_alert_center.html
```

## Ploturi sterse

Am eliminat ploturile care arata mai mult diagnostic intern sau slabiciuni locale decat valoare de demo:

- distributie de erori;
- MAE pe categorii;
- WAPE rolling-window pe categorii;
- outlier forecast examples;
- legacy forecast pe outlieri.

Aceste fisiere pot fi utile intern cand lucrezi la model, dar nu sunt potrivite pentru prezentarea finala.
