# Machine Learning — Stock Optimizer

## Overview

The ML component is responsible for forecasting automotive parts demand and generating recommendations.

---

## Responsibilities

The ML component:
- analyzes CSV data
- cleans the data
- trains the model
- generates forecasts
- exports results for backend import

---

## Input Data

CSV with historical data:

```text
date
sku
quantity_sold
```
---

## Processing Steps

1. Load CSV
2. Clean data
3. Analyze data
4. Feature engineering
5. Train model
6. Evaluate model
7. Generate output

---

## Models

Simple
    -> moving average
    -> Prophet
Advanced
    -> XGBoost
    -> LightGBM

--- 

## Suggestions for Ouput

forecast_output.csv

    sku,forecast_date,predicted_demand,confidence_score,model_name

recommendations_output.csv

    sku,recommendation_type,quantity,priority,reason

---

## Integration

CSV → ML → output CSV → Backend → Database → Frontend

--- 
