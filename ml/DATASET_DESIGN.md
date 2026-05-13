# Dataset design

## Locații UE și climate zones

Datasetul folosește 12 locații UE, fiecare cu o zonă climatică și un calendar sezonier diferit:

| Location ID | Oraș | Țară | Climate zone | Start cerere iarnă |
|---|---|---|---|---|
| FI_HEL | Helsinki | FI | nordic_cold | septembrie |
| SE_STO | Stockholm | SE | nordic_cold | septembrie |
| EE_TLL | Tallinn | EE | baltic_cold | septembrie |
| DK_CPH | Copenhagen | DK | north_maritime | octombrie |
| NL_AMS | Amsterdam | NL | west_maritime | octombrie |
| DE_BER | Berlin | DE | central_continental | octombrie |
| PL_WAW | Warsaw | PL | central_continental | octombrie |
| CZ_PRG | Prague | CZ | central_continental | octombrie |
| RO_BUC | Bucharest | RO | south_east_continental | noiembrie |
| IT_MIL | Milan | IT | south_alpine | noiembrie |
| ES_MAD | Madrid | ES | south_warm | decembrie |
| FR_PAR | Paris | FR | west_temperate | octombrie |

## Parametri exogeni

### Meteo

`weather_daily.csv` conține:

- `temperature_c`;
- `temp_change_1d_c`;
- `temp_change_3d_c`;
- `abs_temp_change_3d_c`;
- `rain_mm`;
- `snow_cm`;
- `cold_snap_flag`;
- `heatwave_flag`;
- `weather_spike_flag`;
- `temperature_drop_flag`;
- `temperature_rise_flag`.

### Calendar

`calendar_daily.csv` și `calendar_events.csv` conțin:

- `is_payday`, `is_payday_window`;
- `is_holiday`, `is_school_holiday`;
- `event_name`, `event_type`;
- `affected_categories`;
- `event_multiplier`;
- `promotion_flag`, `service_campaign_flag`.

## Reguli de generare a cererii

- Lichidul de parbriz de iarnă crește mai devreme în nord și mai târziu în sud.
- Bateriile cresc la cold snap și scăderi bruște de temperatură.
- Ștergătoarele cresc la ploaie, ninsoare și schimbări meteo bruște.
- A/C refill, filtrele de habitaclu și lichidul de răcire cresc la heatwave.
- Produsele de mentenanță cresc în ferestre de salariu și înaintea vacanțelor/călătoriilor.
- Anvelopele de iarnă cresc în campania de iarnă, cu start diferit pe zone climatice.
- Anvelopele de vară cresc în campania de primăvară.

## Fișiere de validare

- `seasonality_checks.csv`: medii lunare pe SKU și locație.
- `exogenous_spike_checks.csv`: uplift ratios pentru payday, weather spike, cold snap și heatwave.
