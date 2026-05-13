from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LocationProfile:
    location_id: str
    city: str
    country: str
    country_code: str
    timezone: str
    latitude: float
    longitude: float
    climate_zone: str
    demand_scale: float
    temp_mean_c: float
    temp_amplitude_c: float
    winter_start_month: int
    winter_end_month: int
    salary_days: Tuple[int, ...]
    payday_last_business_day: bool = True


LOCATIONS: List[LocationProfile] = [
    LocationProfile("FI_HEL", "Helsinki", "Finland", "FI", "Europe/Helsinki", 60.1699, 24.9384, "nordic_cold", 0.78, 5.4, 16.5, 9, 4, (25,)),
    LocationProfile("SE_STO", "Stockholm", "Sweden", "SE", "Europe/Stockholm", 59.3293, 18.0686, "nordic_cold", 0.86, 7.2, 14.8, 9, 4, (25,)),
    LocationProfile("EE_TLL", "Tallinn", "Estonia", "EE", "Europe/Tallinn", 59.4370, 24.7536, "baltic_cold", 0.62, 6.3, 15.5, 9, 4, (10, 25)),
    LocationProfile("DK_CPH", "Copenhagen", "Denmark", "DK", "Europe/Copenhagen", 55.6761, 12.5683, "north_maritime", 0.82, 8.9, 11.2, 10, 3, (25,)),
    LocationProfile("NL_AMS", "Amsterdam", "Netherlands", "NL", "Europe/Amsterdam", 52.3676, 4.9041, "west_maritime", 0.94, 10.1, 10.0, 10, 3, (25,)),
    LocationProfile("DE_BER", "Berlin", "Germany", "DE", "Europe/Berlin", 52.5200, 13.4050, "central_continental", 1.14, 9.8, 12.6, 10, 3, (25,)),
    LocationProfile("PL_WAW", "Warsaw", "Poland", "PL", "Europe/Warsaw", 52.2297, 21.0122, "central_continental", 0.98, 8.7, 13.9, 10, 4, (10, 25)),
    LocationProfile("CZ_PRG", "Prague", "Czechia", "CZ", "Europe/Prague", 50.0755, 14.4378, "central_continental", 0.82, 9.1, 13.1, 10, 3, (15, 25)),
    LocationProfile("RO_BUC", "Bucharest", "Romania", "RO", "Europe/Bucharest", 44.4268, 26.1025, "south_east_continental", 0.90, 11.5, 15.0, 11, 3, (15, 30)),
    LocationProfile("IT_MIL", "Milan", "Italy", "IT", "Europe/Rome", 45.4642, 9.1900, "south_alpine", 1.02, 13.1, 12.2, 11, 2, (27,)),
    LocationProfile("ES_MAD", "Madrid", "Spain", "ES", "Europe/Madrid", 40.4168, -3.7038, "south_warm", 1.00, 15.2, 11.7, 12, 2, (28,)),
    LocationProfile("FR_PAR", "Paris", "France", "FR", "Europe/Paris", 48.8566, 2.3522, "west_temperate", 1.20, 11.6, 10.8, 10, 3, (25,)),
]

PARTS: List[Dict[str, object]] = [
    {"sku": "PEU-WF-WINTER-5L", "part_name": "Lichid parbriz iarna -20C 5L", "category": "winter_fluids", "seasonality_profile": "winter_cold", "base_demand": 3.2, "unit_price_eur": 7.9, "salary_sensitivity": 0.10, "lead_time_days": 5, "min_order_qty": 60, "supplier_id": "SUP-FLUIDS-EU"},
    {"sku": "PEU-WF-SUMMER-5L", "part_name": "Lichid parbriz vara 5L", "category": "summer_fluids", "seasonality_profile": "summer_travel", "base_demand": 2.4, "unit_price_eur": 5.5, "salary_sensitivity": 0.08, "lead_time_days": 4, "min_order_qty": 48, "supplier_id": "SUP-FLUIDS-EU"},
    {"sku": "PEU-WIPER-650", "part_name": "Stergatoare fata 650mm", "category": "wipers", "seasonality_profile": "rain_winter", "base_demand": 1.55, "unit_price_eur": 24.0, "salary_sensitivity": 0.14, "lead_time_days": 6, "min_order_qty": 24, "supplier_id": "SUP-ACCESS-EU"},
    {"sku": "PEU-BATT-70AH", "part_name": "Baterie 70Ah AGM/EFB", "category": "battery", "seasonality_profile": "cold_snap", "base_demand": 0.72, "unit_price_eur": 139.0, "salary_sensitivity": 0.24, "lead_time_days": 7, "min_order_qty": 12, "supplier_id": "SUP-ELECTRIC-DE"},
    {"sku": "PEU-ANTIFREEZE-G12", "part_name": "Antigel G12 concentrat 1L", "category": "coolant", "seasonality_profile": "winter_cold", "base_demand": 1.25, "unit_price_eur": 8.5, "salary_sensitivity": 0.10, "lead_time_days": 5, "min_order_qty": 36, "supplier_id": "SUP-FLUIDS-EU"},
    {"sku": "PEU-CABIN-FILTER-CARBON", "part_name": "Filtru habitaclu cu carbon", "category": "filters", "seasonality_profile": "pollen_heat", "base_demand": 2.10, "unit_price_eur": 18.5, "salary_sensitivity": 0.18, "lead_time_days": 6, "min_order_qty": 36, "supplier_id": "SUP-FILTERS-FR"},
    {"sku": "PEU-AIR-FILTER", "part_name": "Filtru aer motor", "category": "filters", "seasonality_profile": "spring_service", "base_demand": 1.45, "unit_price_eur": 16.0, "salary_sensitivity": 0.16, "lead_time_days": 6, "min_order_qty": 36, "supplier_id": "SUP-FILTERS-FR"},
    {"sku": "PEU-OIL-5W30-5L", "part_name": "Ulei motor 5W30 5L", "category": "maintenance", "seasonality_profile": "steady_salary_travel", "base_demand": 2.75, "unit_price_eur": 47.0, "salary_sensitivity": 0.26, "lead_time_days": 5, "min_order_qty": 48, "supplier_id": "SUP-MAINT-DE"},
    {"sku": "PEU-OIL-FILTER", "part_name": "Filtru ulei", "category": "maintenance", "seasonality_profile": "steady_salary_travel", "base_demand": 2.55, "unit_price_eur": 11.5, "salary_sensitivity": 0.24, "lead_time_days": 5, "min_order_qty": 48, "supplier_id": "SUP-FILTERS-FR"},
    {"sku": "PEU-BRAKE-PADS-F", "part_name": "Placute frana fata", "category": "brakes", "seasonality_profile": "steady_travel", "base_demand": 1.15, "unit_price_eur": 69.0, "salary_sensitivity": 0.22, "lead_time_days": 8, "min_order_qty": 18, "supplier_id": "SUP-BRAKES-IT"},
    {"sku": "PEU-AC-REFILL", "part_name": "Kit incarcare clima R134a/R1234yf", "category": "ac_cooling", "seasonality_profile": "summer_heat", "base_demand": 0.62, "unit_price_eur": 59.0, "salary_sensitivity": 0.16, "lead_time_days": 7, "min_order_qty": 18, "supplier_id": "SUP-CLIMATE-ES"},
    {"sku": "PEU-COOLANT-5L", "part_name": "Lichid racire premix 5L", "category": "coolant", "seasonality_profile": "temp_extremes", "base_demand": 1.05, "unit_price_eur": 22.0, "salary_sensitivity": 0.12, "lead_time_days": 5, "min_order_qty": 30, "supplier_id": "SUP-FLUIDS-EU"},
    {"sku": "PEU-HEADLIGHT-H7", "part_name": "Bec far H7", "category": "lighting", "seasonality_profile": "winter_dark", "base_demand": 1.25, "unit_price_eur": 9.0, "salary_sensitivity": 0.09, "lead_time_days": 4, "min_order_qty": 40, "supplier_id": "SUP-ELECTRIC-DE"},
    {"sku": "PEU-WINTER-TIRE-205", "part_name": "Anvelopa iarna 205/55R16", "category": "tires", "seasonality_profile": "winter_tire_change", "base_demand": 0.52, "unit_price_eur": 92.0, "salary_sensitivity": 0.30, "lead_time_days": 10, "min_order_qty": 16, "supplier_id": "SUP-TIRES-PL"},
    {"sku": "PEU-SUMMER-TIRE-205", "part_name": "Anvelopa vara 205/55R16", "category": "tires", "seasonality_profile": "spring_tire_change", "base_demand": 0.48, "unit_price_eur": 82.0, "salary_sensitivity": 0.28, "lead_time_days": 10, "min_order_qty": 16, "supplier_id": "SUP-TIRES-PL"},
    {"sku": "PEU-ADBLUE-10L", "part_name": "AdBlue 10L", "category": "consumables", "seasonality_profile": "travel", "base_demand": 1.65, "unit_price_eur": 14.0, "salary_sensitivity": 0.12, "lead_time_days": 4, "min_order_qty": 60, "supplier_id": "SUP-FLUIDS-EU"},
    {"sku": "PEU-RUBBER-MATS", "part_name": "Covorase cauciuc Peugeot", "category": "accessories", "seasonality_profile": "autumn_winter", "base_demand": 0.58, "unit_price_eur": 39.0, "salary_sensitivity": 0.20, "lead_time_days": 8, "min_order_qty": 18, "supplier_id": "SUP-ACCESS-EU"},
    {"sku": "PEU-SPARK-PLUG", "part_name": "Bujie benzina", "category": "maintenance", "seasonality_profile": "steady", "base_demand": 0.95, "unit_price_eur": 12.0, "salary_sensitivity": 0.13, "lead_time_days": 6, "min_order_qty": 32, "supplier_id": "SUP-MAINT-DE"},
]

SUPPLIERS: List[Dict[str, object]] = [
    {"supplier_id": "SUP-FLUIDS-EU", "supplier_name": "EuroFluids Logistics", "country_code": "DE", "reliability_score": 0.93, "avg_delay_days": 0.6},
    {"supplier_id": "SUP-ACCESS-EU", "supplier_name": "AutoAccess Distribution", "country_code": "NL", "reliability_score": 0.90, "avg_delay_days": 0.9},
    {"supplier_id": "SUP-ELECTRIC-DE", "supplier_name": "Rhine Electric Parts", "country_code": "DE", "reliability_score": 0.91, "avg_delay_days": 0.8},
    {"supplier_id": "SUP-FILTERS-FR", "supplier_name": "Filtres Auto France", "country_code": "FR", "reliability_score": 0.92, "avg_delay_days": 0.7},
    {"supplier_id": "SUP-MAINT-DE", "supplier_name": "DACH Maintenance Parts", "country_code": "DE", "reliability_score": 0.94, "avg_delay_days": 0.5},
    {"supplier_id": "SUP-BRAKES-IT", "supplier_name": "Nord Italia Braking", "country_code": "IT", "reliability_score": 0.88, "avg_delay_days": 1.1},
    {"supplier_id": "SUP-CLIMATE-ES", "supplier_name": "Iberia Climate Systems", "country_code": "ES", "reliability_score": 0.87, "avg_delay_days": 1.3},
    {"supplier_id": "SUP-TIRES-PL", "supplier_name": "Central Europe Tyres", "country_code": "PL", "reliability_score": 0.89, "avg_delay_days": 1.0},
]


def _daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _easter_date(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _last_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    d = next_month - timedelta(days=1)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def _last_business_day(year: int, month: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _timestamp_for_date(d: date, timezone: str, hour: int = 18) -> Tuple[str, str]:
    local = datetime.combine(d, time(hour, 0), tzinfo=ZoneInfo(timezone))
    utc = local.astimezone(ZoneInfo("UTC"))
    return local.isoformat(), utc.isoformat()


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _month_distance(month: int, center: int) -> int:
    direct = abs(month - center)
    return min(direct, 12 - direct)


def _window_days(d: date, start_md: Tuple[int, int], end_md: Tuple[int, int]) -> bool:
    start = date(d.year, start_md[0], start_md[1])
    end = date(d.year, end_md[0], end_md[1])
    if start <= end:
        return start <= d <= end
    return d >= start or d <= end


def generate_locations_df() -> pd.DataFrame:
    return pd.DataFrame([loc.__dict__ for loc in LOCATIONS])


def generate_parts_df() -> pd.DataFrame:
    return pd.DataFrame(PARTS)


def generate_suppliers_df() -> pd.DataFrame:
    return pd.DataFrame(SUPPLIERS)


def generate_weather_daily(start: date, end: date, rng: np.random.Generator) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    all_dates = list(_daterange(start, end))
    for loc in LOCATIONS:
        n = len(all_dates)
        noise = np.zeros(n)
        noise[0] = rng.normal(0, 1.6)
        for i in range(1, n):
            noise[i] = 0.82 * noise[i - 1] + rng.normal(0, 1.35)

        shock = np.zeros(n)
        years = sorted({d.year for d in all_dates})
        for y in years:
            cold_events = {
                "nordic_cold": 5,
                "baltic_cold": 5,
                "north_maritime": 3,
                "west_maritime": 2,
                "central_continental": 4,
                "south_east_continental": 3,
                "south_alpine": 2,
                "south_warm": 1,
                "west_temperate": 2,
            }.get(loc.climate_zone, 3)
            for _ in range(cold_events):
                cold_months = [9, 10, 11, 12, 1, 2, 3, 4] if loc.winter_start_month <= 9 else [11, 12, 1, 2, 3]
                m = int(rng.choice(cold_months))
                day_max = 28 if m == 2 else 30
                s = date(y if m >= loc.winter_start_month or m >= 9 else y, m, int(rng.integers(1, day_max)))
                duration = int(rng.integers(2, 6))
                drop = float(rng.uniform(5.5, 11.0))
                for j, dd in enumerate(all_dates):
                    if s <= dd < s + timedelta(days=duration):
                        shock[j] -= drop * (1.0 - 0.12 * abs((dd - s).days))
            heat_events = {
                "nordic_cold": 1,
                "baltic_cold": 1,
                "north_maritime": 1,
                "west_maritime": 2,
                "central_continental": 3,
                "south_east_continental": 4,
                "south_alpine": 4,
                "south_warm": 5,
                "west_temperate": 2,
            }.get(loc.climate_zone, 2)
            for _ in range(heat_events):
                m = int(rng.choice([6, 7, 8]))
                s = date(y, m, int(rng.integers(1, 25)))
                duration = int(rng.integers(3, 8))
                rise = float(rng.uniform(4.5, 9.5))
                for j, dd in enumerate(all_dates):
                    if s <= dd < s + timedelta(days=duration):
                        shock[j] += rise * (1.0 - 0.08 * abs((dd - s).days))

        temps = []
        for i, d in enumerate(all_dates):
            doy = d.timetuple().tm_yday
            seasonal = loc.temp_mean_c + loc.temp_amplitude_c * math.sin(2 * math.pi * (doy - 172) / 365.25)
            temp = seasonal + noise[i] + shock[i]
            temps.append(float(round(temp, 1)))

        temp_series = pd.Series(temps)
        temp_change_1d = temp_series.diff().fillna(0.0)
        temp_change_3d = temp_series.diff(3).fillna(0.0)

        for i, d in enumerate(all_dates):
            month = d.month
            is_cold = temps[i] <= 1.0
            rain_base = 0.22
            if loc.climate_zone in ("north_maritime", "west_maritime", "west_temperate"):
                rain_base += 0.10
            if month in (10, 11, 12, 1, 2, 3):
                rain_base += 0.07
            if loc.climate_zone == "south_warm" and month in (7, 8):
                rain_base -= 0.12
            has_precip = rng.random() < max(0.05, min(0.55, rain_base))
            rain_mm = 0.0
            snow_cm = 0.0
            if has_precip:
                amount = float(rng.gamma(1.8, 3.5))
                if is_cold:
                    snow_cm = round(amount * rng.uniform(0.6, 1.7), 1)
                    rain_mm = round(amount * rng.uniform(0.0, 0.25), 1)
                else:
                    rain_mm = round(amount, 1)
            local_ts, utc_ts = _timestamp_for_date(d, loc.timezone, hour=12)
            temp_3d = float(round(temp_change_3d.iloc[i], 1))
            temp_1d = float(round(temp_change_1d.iloc[i], 1))
            heat_threshold = 26.0 if loc.climate_zone in ("nordic_cold", "baltic_cold") else 29.0
            rows.append(
                {
                    "timestamp": local_ts,
                    "timestamp_utc": utc_ts,
                    "date": d.isoformat(),
                    "location_id": loc.location_id,
                    "city": loc.city,
                    "country_code": loc.country_code,
                    "climate_zone": loc.climate_zone,
                    "temperature_c": temps[i],
                    "temp_change_1d_c": temp_1d,
                    "temp_change_3d_c": temp_3d,
                    "abs_temp_change_3d_c": abs(temp_3d),
                    "rain_mm": rain_mm,
                    "snow_cm": snow_cm,
                    "cold_snap_flag": int(temp_3d <= -6.0 or temps[i] <= -6.0),
                    "heatwave_flag": int(temps[i] >= heat_threshold or (temp_3d >= 6.0 and temps[i] >= 23.0)),
                    "weather_spike_flag": int(abs(temp_3d) >= 6.0),
                    "temperature_drop_flag": int(temp_3d <= -6.0),
                    "temperature_rise_flag": int(temp_3d >= 6.0),
                }
            )
    return pd.DataFrame(rows)


def generate_calendar_daily(start: date, end: date) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows: List[Dict[str, object]] = []
    event_rows: List[Dict[str, object]] = []
    all_dates = list(_daterange(start, end))
    easters = {y: _easter_date(y) for y in sorted({d.year for d in all_dates})}
    black_fridays = {y: _last_friday(y, 11) for y in easters}

    for loc in LOCATIONS:
        for d in all_dates:
            local_ts, utc_ts = _timestamp_for_date(d, loc.timezone, hour=0)
            payday_exact = False
            payday_window = False
            salary_dates = [date(d.year, d.month, min(day, 28 if d.month == 2 else 30)) for day in loc.salary_days]
            if loc.payday_last_business_day:
                salary_dates.append(_last_business_day(d.year, d.month))
            for sd in salary_dates:
                if d == sd:
                    payday_exact = True
                if abs((d - sd).days) <= 1:
                    payday_window = True

            names: List[str] = []
            types: List[str] = []
            affected_categories: List[str] = []
            event_multiplier = 1.0
            is_holiday = 0
            is_school_holiday = 0
            promotion_flag = 0
            service_campaign_flag = 0

            if payday_window:
                names.append("salary_window")
                types.append("payday")
                affected_categories.extend(["maintenance", "brakes", "tires", "battery"])
                event_multiplier *= 1.10 if payday_exact else 1.06

            if d.month == 1 and d.day == 1:
                names.append("new_year_closed")
                types.append("public_holiday")
                is_holiday = 1
                event_multiplier *= 0.65
            if d.month == 5 and d.day == 1:
                names.append("may_day")
                types.append("public_holiday")
                is_holiday = 1
                event_multiplier *= 0.82
            if d.month == 12 and d.day in (24, 25, 26):
                names.append("winter_holiday")
                types.append("public_holiday")
                is_holiday = 1
                is_school_holiday = 1
                event_multiplier *= 0.75

            easter = easters[d.year]
            if easter - timedelta(days=3) <= d <= easter + timedelta(days=2):
                names.append("easter_travel_window")
                types.append("holiday_travel")
                affected_categories.extend(["maintenance", "wipers", "brakes", "consumables"])
                event_multiplier *= 1.12
                if d in (easter, easter + timedelta(days=1)):
                    is_holiday = 1

            if date(d.year, 6, 15) <= d <= date(d.year, 7, 15):
                names.append("summer_road_trip_start")
                types.append("holiday_travel")
                affected_categories.extend(["maintenance", "summer_fluids", "consumables", "filters"])
                event_multiplier *= 1.16
            if date(d.year, 7, 20) <= d <= date(d.year, 8, 20):
                names.append("summer_holiday_season")
                types.append("school_holiday")
                affected_categories.extend(["maintenance", "consumables", "ac_cooling"])
                is_school_holiday = 1
                event_multiplier *= 1.08
            if date(d.year, 12, 15) <= d <= date(d.year, 12, 31):
                names.append("winter_travel_window")
                types.append("holiday_travel")
                affected_categories.extend(["winter_fluids", "wipers", "battery", "maintenance", "lighting"])
                event_multiplier *= 1.15

            bf = black_fridays[d.year]
            if bf - timedelta(days=3) <= d <= bf + timedelta(days=3):
                names.append("black_friday_service_promo")
                types.append("promotion")
                affected_categories.extend(["maintenance", "filters", "accessories", "tires"])
                promotion_flag = 1
                service_campaign_flag = 1
                event_multiplier *= 1.18

            if loc.winter_start_month == 9:
                winter_ready_start, winter_ready_end = (9, 1), (10, 31)
                spring_tire_start, spring_tire_end = (3, 15), (5, 5)
            elif loc.winter_start_month == 10:
                winter_ready_start, winter_ready_end = (10, 1), (11, 30)
                spring_tire_start, spring_tire_end = (3, 20), (5, 15)
            elif loc.winter_start_month == 11:
                winter_ready_start, winter_ready_end = (10, 20), (12, 10)
                spring_tire_start, spring_tire_end = (3, 1), (4, 30)
            else:
                winter_ready_start, winter_ready_end = (11, 1), (12, 20)
                spring_tire_start, spring_tire_end = (2, 15), (4, 15)

            if _window_days(d, winter_ready_start, winter_ready_end):
                names.append("winter_readiness_campaign")
                types.append("seasonal_campaign")
                affected_categories.extend(["winter_fluids", "battery", "wipers", "tires", "coolant", "lighting", "accessories"])
                service_campaign_flag = 1
                event_multiplier *= 1.10

            if _window_days(d, spring_tire_start, spring_tire_end):
                names.append("spring_service_campaign")
                types.append("seasonal_campaign")
                affected_categories.extend(["summer_fluids", "filters", "tires", "maintenance"])
                service_campaign_flag = 1
                event_multiplier *= 1.08

            pollen_start = date(d.year, 3, 15) if loc.climate_zone in ("south_warm", "south_alpine", "south_east_continental") else date(d.year, 4, 1)
            pollen_end = date(d.year, 5, 31) if loc.climate_zone in ("south_warm", "south_alpine") else date(d.year, 6, 15)
            if pollen_start <= d <= pollen_end:
                names.append("pollen_filter_season")
                types.append("seasonal_demand")
                affected_categories.extend(["filters"])
                event_multiplier *= 1.05

            if not names:
                names = ["none"]
                types = ["none"]
                affected_categories = ["none"]

            row = {
                "timestamp": local_ts,
                "timestamp_utc": utc_ts,
                "date": d.isoformat(),
                "location_id": loc.location_id,
                "city": loc.city,
                "country_code": loc.country_code,
                "is_payday": int(payday_exact),
                "is_payday_window": int(payday_window),
                "is_holiday": int(is_holiday),
                "is_school_holiday": int(is_school_holiday),
                "event_name": "|".join(dict.fromkeys(names)),
                "event_type": "|".join(dict.fromkeys(types)),
                "affected_categories": "|".join(dict.fromkeys(affected_categories)),
                "event_multiplier": round(float(event_multiplier), 3),
                "promotion_flag": int(promotion_flag),
                "service_campaign_flag": int(service_campaign_flag),
            }
            rows.append(row)
            if row["event_name"] != "none":
                event_rows.append(row.copy())
    return pd.DataFrame(rows), pd.DataFrame(event_rows)


def _winter_profile_multiplier(d: date, loc: LocationProfile) -> float:
    m = d.month
    if loc.winter_start_month == 9:
        if m == 9:
            return 1.55
        if m in (10, 11):
            return 2.30
        if m in (12, 1, 2):
            return 2.90
        if m in (3, 4):
            return 1.50
    elif loc.winter_start_month == 10:
        if m == 10:
            return 1.45
        if m in (11, 12, 1, 2):
            return 2.35
        if m == 3:
            return 1.30
    elif loc.winter_start_month == 11:
        if m == 10:
            return 1.10
        if m == 11:
            return 1.50
        if m in (12, 1, 2):
            return 2.00
        if m == 3:
            return 1.15
    else:
        if m in (11, 12, 1, 2):
            return 1.45
    return 0.72 if m in (6, 7, 8) else 0.95


def _tire_winter_multiplier(d: date, loc: LocationProfile) -> float:
    m = d.month
    if loc.winter_start_month == 9:
        return {8: 1.15, 9: 2.70, 10: 3.30, 11: 2.00, 12: 1.20, 3: 0.80}.get(m, 0.45)
    if loc.winter_start_month == 10:
        return {9: 1.20, 10: 2.70, 11: 3.10, 12: 1.50, 3: 0.70}.get(m, 0.45)
    if loc.winter_start_month == 11:
        return {10: 1.45, 11: 2.50, 12: 2.20, 1: 1.00, 3: 0.55}.get(m, 0.40)
    return {11: 1.70, 12: 1.90, 1: 1.00}.get(m, 0.32)


def _tire_summer_multiplier(d: date, loc: LocationProfile) -> float:
    m = d.month
    if loc.winter_start_month in (9, 10):
        return {3: 1.40, 4: 3.20, 5: 2.30, 6: 1.10, 10: 0.40, 11: 0.35}.get(m, 0.60)
    return {2: 1.20, 3: 2.70, 4: 2.80, 5: 1.60, 11: 0.40, 12: 0.35}.get(m, 0.62)


def _category_event_multiplier(category: str, profile: str, calendar_row: pd.Series) -> float:
    affected = str(calendar_row.get("affected_categories", ""))
    event_type = str(calendar_row.get("event_type", ""))
    multiplier = 1.0
    if category in affected or "none" not in affected:
        if category in affected:
            multiplier *= 1.0 + min(0.35, max(0.0, float(calendar_row.get("event_multiplier", 1.0)) - 1.0) * 1.35)
    if "promotion" in event_type:
        if category in ("maintenance", "filters", "accessories", "tires"):
            multiplier *= 1.18
        else:
            multiplier *= 1.06
    if "holiday_travel" in event_type:
        if category in ("maintenance", "brakes", "wipers", "consumables", "summer_fluids"):
            multiplier *= 1.16
        if category in ("winter_fluids", "lighting", "battery"):
            multiplier *= 1.08
    if "payday" in event_type:
        multiplier *= 1.03
    if "seasonal_campaign" in event_type and category in affected:
        multiplier *= 1.15
    if "seasonal_demand" in event_type and category in affected:
        multiplier *= 1.18
    return multiplier


def _weather_multiplier(part: Dict[str, object], loc: LocationProfile, weather_row: pd.Series) -> Tuple[float, float]:
    profile = str(part["seasonality_profile"])
    category = str(part["category"])
    temp = float(weather_row["temperature_c"])
    temp3 = float(weather_row["temp_change_3d_c"])
    rain = float(weather_row["rain_mm"])
    snow = float(weather_row["snow_cm"])
    cold_snap = int(weather_row["cold_snap_flag"])
    heatwave = int(weather_row["heatwave_flag"])
    spike_flag = int(weather_row["weather_spike_flag"])
    multiplier = 1.0
    spike_component = 1.0

    if category == "winter_fluids":
        if temp < 5:
            multiplier *= 1.0 + min(1.15, (5 - temp) * 0.055)
        if temp < 0:
            multiplier *= 1.25
        if cold_snap:
            multiplier *= 1.75
            spike_component *= 1.75
        if snow > 0:
            multiplier *= 1.25
        if rain > 8:
            multiplier *= 1.10
        if spike_flag and temp3 < -5:
            multiplier *= 1.30
            spike_component *= 1.30
    elif category == "battery":
        if temp < 0:
            multiplier *= 1.0 + min(1.0, abs(temp) * 0.05)
        if cold_snap:
            multiplier *= 2.05
            spike_component *= 2.05
        if spike_flag and temp3 < -5:
            multiplier *= 1.35
            spike_component *= 1.35
    elif category == "wipers":
        if rain > 5:
            multiplier *= 1.30
        if rain > 15:
            multiplier *= 1.55
        if snow > 0:
            multiplier *= 1.35
        if spike_flag:
            multiplier *= 1.12
            spike_component *= 1.12
    elif category == "coolant":
        if temp < 0:
            multiplier *= 1.30
        if temp > 27:
            multiplier *= 1.35
        if cold_snap or heatwave:
            multiplier *= 1.35
            spike_component *= 1.35
    elif category == "ac_cooling":
        if temp > 22:
            multiplier *= 1.0 + min(1.45, (temp - 22) * 0.075)
        if heatwave:
            multiplier *= 1.80
            spike_component *= 1.80
        if spike_flag and temp3 > 5:
            multiplier *= 1.25
            spike_component *= 1.25
    elif category == "filters":
        if temp > 20:
            multiplier *= 1.08
        if heatwave and profile == "pollen_heat":
            multiplier *= 1.25
            spike_component *= 1.25
    elif category == "lighting":
        if temp < 5:
            multiplier *= 1.15
        if loc.climate_zone in ("nordic_cold", "baltic_cold") and temp < 2:
            multiplier *= 1.20
        if snow > 0:
            multiplier *= 1.12
    elif category == "accessories":
        if rain > 8 or snow > 0:
            multiplier *= 1.25
        if cold_snap:
            multiplier *= 1.20
    elif category == "consumables":
        if temp > 25:
            multiplier *= 1.08
    return multiplier, spike_component


def _seasonality_multiplier(part: Dict[str, object], loc: LocationProfile, d: date) -> float:
    profile = str(part["seasonality_profile"])
    category = str(part["category"])
    m = d.month
    mult = 1.0
    if profile == "winter_cold":
        mult *= _winter_profile_multiplier(d, loc)
    elif profile == "rain_winter":
        mult *= 1.20 if m in (10, 11, 12, 1, 2, 3) else 0.88
    elif profile == "cold_snap":
        mult *= 1.45 if m in (11, 12, 1, 2, 3) else 0.80
    elif profile == "pollen_heat":
        mult *= 1.70 if m in (4, 5, 6) else 1.25 if m in (7, 8) else 0.86
    elif profile == "spring_service":
        mult *= 1.65 if m in (3, 4, 5) else 1.10 if m in (6, 7) else 0.90
    elif profile == "steady_salary_travel":
        mult *= 1.18 if m in (6, 7, 8, 12) else 0.96
    elif profile == "steady_travel":
        mult *= 1.15 if m in (6, 7, 8, 12) else 0.98
    elif profile == "summer_heat":
        mult *= 1.95 if m in (6, 7, 8) else 1.30 if m == 5 else 0.55
    elif profile == "temp_extremes":
        mult *= 1.18 if m in (6, 7, 8, 11, 12, 1, 2) else 0.95
    elif profile == "winter_dark":
        mult *= 1.55 if m in (10, 11, 12, 1, 2) else 0.82
    elif profile == "winter_tire_change":
        mult *= _tire_winter_multiplier(d, loc)
    elif profile == "spring_tire_change":
        mult *= _tire_summer_multiplier(d, loc)
    elif profile == "travel":
        mult *= 1.22 if m in (6, 7, 8, 12) else 0.96
    elif profile == "autumn_winter":
        mult *= 1.75 if m in (9, 10, 11, 12, 1) else 0.65
    elif profile == "summer_travel":
        mult *= 1.45 if m in (5, 6, 7, 8) else 0.75 if m in (12, 1, 2) else 1.0
    if category == "tires" and loc.climate_zone == "south_warm":
        mult *= 0.78 if "winter" in profile else 1.10
    return mult


def _fuel_price(d: date, loc: LocationProfile) -> float:
    t = (d - date(2023, 1, 1)).days
    base_by_zone = {
        "nordic_cold": 1.88,
        "baltic_cold": 1.70,
        "north_maritime": 1.82,
        "west_maritime": 1.86,
        "west_temperate": 1.84,
        "central_continental": 1.76,
        "south_east_continental": 1.58,
        "south_alpine": 1.82,
        "south_warm": 1.66,
    }
    return round(base_by_zone.get(loc.climate_zone, 1.75) + 0.05 * math.sin(2 * math.pi * t / 365.25) + 0.00004 * t, 3)


def _mobility_index(d: date) -> float:
    base = 100.0
    if d.weekday() in (5, 6):
        base += 8.0
    if d.month in (7, 8, 12):
        base += 10.0
    if d.month in (1, 2):
        base -= 3.0
    return round(base, 1)


def generate_sales_history(
    start: date,
    end: date,
    locations_df: pd.DataFrame,
    parts_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    calendar_df: pd.DataFrame,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    weather_idx = weather_df.set_index(["date", "location_id"]).to_dict("index")
    calendar_idx = calendar_df.set_index(["date", "location_id"]).to_dict("index")
    rows: List[Dict[str, object]] = []
    inventory_rows: List[Dict[str, object]] = []
    all_dates = list(_daterange(start, end))
    parts = parts_df.to_dict(orient="records")
    loc_map = {loc.location_id: loc for loc in LOCATIONS}

    for loc in LOCATIONS:
        for part in parts:
            base_demand = float(part["base_demand"]) * loc.demand_scale
            lead_time_days = int(part["lead_time_days"])
            min_order_qty = int(part["min_order_qty"])
            avg_reference = max(0.25, base_demand * 1.35)
            safety_stock = int(math.ceil(avg_reference * (lead_time_days + 5)))
            reorder_point = int(math.ceil(avg_reference * (lead_time_days + 4)))
            target_stock = max(min_order_qty, int(math.ceil(avg_reference * 34)))
            stock = float(target_stock + rng.integers(0, max(2, min_order_qty)))
            pending_orders: List[Tuple[date, int]] = []
            last_order_date: date | None = None
            stockouts = 0
            total_sales = 0
            total_latent = 0

            for d in all_dates:
                for arrival_date, qty in list(pending_orders):
                    if arrival_date <= d:
                        stock += qty
                        pending_orders.remove((arrival_date, qty))

                w = weather_idx[(d.isoformat(), loc.location_id)]
                cal = calendar_idx[(d.isoformat(), loc.location_id)]
                local_ts, utc_ts = _timestamp_for_date(d, loc.timezone, hour=18)
                dow = d.weekday()
                weekday_mult = [1.08, 1.05, 1.03, 1.04, 1.10, 0.72, 0.32][dow]
                season_mult = _seasonality_multiplier(part, loc, d)
                weather_mult, weather_spike_component = _weather_multiplier(part, loc, w)
                event_mult = _category_event_multiplier(str(part["category"]), str(part["seasonality_profile"]), cal)
                salary_mult = 1.0 + float(part["salary_sensitivity"]) * int(cal["is_payday_window"])
                holiday_close_mult = 0.62 if int(cal["is_holiday"]) and "holiday_travel" not in str(cal["event_type"]) else 1.0
                year_trend = 1.0 + 0.035 * (d.year - start.year) + 0.00002 * (d - start).days
                noise_mult = float(rng.lognormal(mean=0.0, sigma=0.18))
                mean_demand = base_demand * weekday_mult * season_mult * weather_mult * event_mult * salary_mult * holiday_close_mult * year_trend * noise_mult
                if rng.random() < 0.006:
                    mean_demand *= float(rng.uniform(1.8, 3.2))
                mean_demand = max(0.02, mean_demand)
                latent_demand = int(rng.poisson(mean_demand))
                sales_qty = int(min(stock, latent_demand))
                stockout_flag = int(sales_qty < latent_demand)
                if stockout_flag:
                    stockouts += 1
                stock = max(0.0, stock - sales_qty)
                total_sales += sales_qty
                total_latent += latent_demand

                severe_weather_delay = int(float(w["snow_cm"]) > 8 or int(w["cold_snap_flag"]) == 1)
                open_pending_qty = sum(q for _, q in pending_orders)
                if stock + open_pending_qty <= reorder_point and (last_order_date is None or (d - last_order_date).days > 3):
                    delay = int(rng.poisson(0.6 + severe_weather_delay * 0.9))
                    order_qty = int(max(min_order_qty, target_stock - stock - open_pending_qty + rng.integers(0, max(2, min_order_qty // 2))))
                    pending_orders.append((d + timedelta(days=lead_time_days + delay), order_qty))
                    last_order_date = d

                unit_price = float(part["unit_price_eur"])
                is_weather_spike_relevant = int(weather_spike_component > 1.05)
                is_salary_spike_relevant = int(int(cal["is_payday_window"]) and float(part["salary_sensitivity"]) >= 0.16)
                is_calendar_spike_relevant = int(event_mult >= 1.12)
                rows.append(
                    {
                        "timestamp": local_ts,
                        "timestamp_utc": utc_ts,
                        "date": d.isoformat(),
                        "sku": part["sku"],
                        "part_name": part["part_name"],
                        "category": part["category"],
                        "seasonality_profile": part["seasonality_profile"],
                        "location_id": loc.location_id,
                        "city": loc.city,
                        "country": loc.country,
                        "country_code": loc.country_code,
                        "climate_zone": loc.climate_zone,
                        "quantity_sold": sales_qty,
                        "latent_demand_signal": latent_demand,
                        "unit_price_eur": unit_price,
                        "revenue_eur": round(sales_qty * unit_price, 2),
                        "stock_on_hand_end": int(round(stock)),
                        "stockout_flag": stockout_flag,
                        "day_of_week": dow,
                        "day_name": d.strftime("%A"),
                        "day_of_month": d.day,
                        "week_of_year": int(pd.Timestamp(d).isocalendar().week),
                        "month": d.month,
                        "quarter": (d.month - 1) // 3 + 1,
                        "year": d.year,
                        "season": _season(d.month),
                        "is_weekend": int(dow >= 5),
                        "temperature_c": float(w["temperature_c"]),
                        "temp_change_1d_c": float(w["temp_change_1d_c"]),
                        "temp_change_3d_c": float(w["temp_change_3d_c"]),
                        "abs_temp_change_3d_c": float(w["abs_temp_change_3d_c"]),
                        "rain_mm": float(w["rain_mm"]),
                        "snow_cm": float(w["snow_cm"]),
                        "cold_snap_flag": int(w["cold_snap_flag"]),
                        "heatwave_flag": int(w["heatwave_flag"]),
                        "weather_spike_flag": int(w["weather_spike_flag"]),
                        "temperature_drop_flag": int(w["temperature_drop_flag"]),
                        "temperature_rise_flag": int(w["temperature_rise_flag"]),
                        "is_payday": int(cal["is_payday"]),
                        "is_payday_window": int(cal["is_payday_window"]),
                        "is_holiday": int(cal["is_holiday"]),
                        "is_school_holiday": int(cal["is_school_holiday"]),
                        "event_name": cal["event_name"],
                        "event_type": cal["event_type"],
                        "affected_categories": cal["affected_categories"],
                        "event_multiplier": float(cal["event_multiplier"]),
                        "promotion_flag": int(cal["promotion_flag"]),
                        "service_campaign_flag": int(cal["service_campaign_flag"]),
                        "fuel_price_eur_l": _fuel_price(d, loc),
                        "mobility_index": _mobility_index(d),
                        "mean_demand_before_stock": round(mean_demand, 4),
                        "weather_spike_applied": is_weather_spike_relevant,
                        "salary_spike_applied": is_salary_spike_relevant,
                        "calendar_spike_applied": is_calendar_spike_relevant,
                    }
                )
            inv_status = "ok"
            if stock <= reorder_point:
                inv_status = "reorder"
            if stock > target_stock * 1.7:
                inv_status = "overstock"
            inventory_rows.append(
                {
                    "snapshot_timestamp": _timestamp_for_date(end, loc.timezone, hour=20)[0],
                    "snapshot_timestamp_utc": _timestamp_for_date(end, loc.timezone, hour=20)[1],
                    "snapshot_date": end.isoformat(),
                    "location_id": loc.location_id,
                    "city": loc.city,
                    "country_code": loc.country_code,
                    "sku": part["sku"],
                    "part_name": part["part_name"],
                    "category": part["category"],
                    "supplier_id": part["supplier_id"],
                    "current_stock": int(round(stock)),
                    "reorder_point": reorder_point,
                    "safety_stock": safety_stock,
                    "optimal_stock": target_stock,
                    "min_order_qty": min_order_qty,
                    "lead_time_days": lead_time_days,
                    "pending_order_qty": int(sum(q for _, q in pending_orders)),
                    "stockout_days_history": stockouts,
                    "total_sales_history": total_sales,
                    "latent_demand_signal_history": total_latent,
                    "inventory_status": inv_status,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(inventory_rows)


def generate_dataset(
    output_dir: str | Path = "data/raw",
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    future_end_date: str = "2026-01-30",
    seed: int = 42,
) -> Dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    by_location = output / "by_location"
    by_location.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    future_end = date.fromisoformat(future_end_date)

    locations_df = generate_locations_df()
    parts_df = generate_parts_df()
    suppliers_df = generate_suppliers_df()
    weather_df = generate_weather_daily(start, future_end, rng)
    calendar_df, events_df = generate_calendar_daily(start, future_end)
    sales_df, inventory_df = generate_sales_history(start, end, locations_df, parts_df, weather_df, calendar_df, rng)

    locations_df.to_csv(output / "eu_locations.csv", index=False)
    parts_df.to_csv(output / "parts_master.csv", index=False)
    suppliers_df.to_csv(output / "suppliers.csv", index=False)
    weather_df.to_csv(output / "weather_daily.csv", index=False)
    calendar_df.to_csv(output / "calendar_daily.csv", index=False)
    events_df.to_csv(output / "calendar_events.csv", index=False)
    sales_df.to_csv(output / "sales_history.csv", index=False)
    inventory_df.to_csv(output / "inventory_snapshot.csv", index=False)

    for loc_id, loc_sales in sales_df.groupby("location_id"):
        loc_sales.to_csv(by_location / f"sales_{loc_id}.csv", index=False)

    dictionary_rows = [
        {"file": "sales_history.csv", "column": "timestamp", "description": "Data si ora locala la finalul zilei de vanzare, ISO-8601 cu timezone."},
        {"file": "sales_history.csv", "column": "quantity_sold", "description": "Unitati vandute; target pentru modelul de forecasting."},
        {"file": "sales_history.csv", "column": "latent_demand_signal", "description": "Cerere sintetica inainte de limitari de stoc; utila pentru analiza, nu este folosita ca target."},
        {"file": "sales_history.csv", "column": "temperature_c", "description": "Temperatura zilnica locala; parametru exogen."},
        {"file": "sales_history.csv", "column": "temp_change_3d_c", "description": "Schimbare de temperatura fata de acum 3 zile; folosita pentru spike-uri."},
        {"file": "sales_history.csv", "column": "weather_spike_flag", "description": "1 daca temperatura s-a schimbat brusc in ultimele 3 zile."},
        {"file": "sales_history.csv", "column": "is_payday_window", "description": "1 in ziua de salariu sau in intervalul +/- 1 zi."},
        {"file": "sales_history.csv", "column": "event_type", "description": "Evenimente calendaristice: payday, holiday_travel, seasonal_campaign, promotion etc."},
        {"file": "weather_daily.csv", "column": "snow_cm", "description": "Zapada estimata, folosita pentru cerere de lichid iarna, stergatoare, baterii."},
        {"file": "calendar_daily.csv", "column": "affected_categories", "description": "Categorii de produse afectate de evenimentul calendaristic."},
        {"file": "inventory_snapshot.csv", "column": "current_stock", "description": "Stoc curent la finalul istoricului, folosit de recomandari."},
    ]
    pd.DataFrame(dictionary_rows).to_csv(output / "dataset_dictionary.csv", index=False)

    summary = {
        "seed": seed,
        "sales_start_date": start_date,
        "sales_end_date": end_date,
        "future_exogenous_end_date": future_end_date,
        "n_locations": int(locations_df.shape[0]),
        "n_skus": int(parts_df.shape[0]),
        "n_sales_rows": int(sales_df.shape[0]),
        "n_weather_rows": int(weather_df.shape[0]),
        "n_calendar_rows": int(calendar_df.shape[0]),
        "generated_files": sorted([str(p.relative_to(output)) for p in output.rglob("*.csv")]),
    }
    (output / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {"output_dir": str(output), **{k: str(output / k) for k in ["sales_history.csv", "weather_daily.csv", "calendar_daily.csv", "inventory_snapshot.csv"]}}


if __name__ == "__main__":
    generate_dataset()
