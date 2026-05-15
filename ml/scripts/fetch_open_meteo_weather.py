from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RAW_DIR = ROOT / "data" / "raw"
DEFAULT_OUTPUT = RAW_DIR / "weather_forecast_open_meteo.csv"
DEFAULT_METADATA = RAW_DIR / "weather_forecast_open_meteo_metadata.json"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_DAILY_VARS = [
    "temperature_2m_mean",
    "temperature_2m_min",
    "temperature_2m_max",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def open_meteo_url(latitude: float, longitude: float, timezone_name: str, forecast_days: int) -> str:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(OPEN_METEO_DAILY_VARS),
        "timezone": timezone_name,
        "forecast_days": forecast_days,
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "timeformat": "iso8601",
    }
    return f"{OPEN_METEO_FORECAST_URL}?{urlencode(params)}"


def request_json(url: str, timeout: int) -> dict:
    request = Request(url, headers={"User-Agent": "stock-optimizer-ml-demo/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def value_at(values: dict, key: str, idx: int, default: float = 0.0) -> float:
    raw = values.get(key, [])
    if idx >= len(raw) or raw[idx] is None:
        return default
    return float(raw[idx])


def fetch_location_forecast(location: pd.Series, forecast_days: int, timeout: int) -> pd.DataFrame:
    url = open_meteo_url(
        latitude=float(location["lat"]),
        longitude=float(location["lon"]),
        timezone_name=str(location.get("timezone", "auto")),
        forecast_days=forecast_days,
    )
    payload = request_json(url, timeout=timeout)
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    if not dates:
        return pd.DataFrame()

    rows = []
    for idx, day in enumerate(dates):
        temp_mean = value_at(daily, "temperature_2m_mean", idx, default=np.nan)
        temp_min = value_at(daily, "temperature_2m_min", idx, default=temp_mean)
        temp_max = value_at(daily, "temperature_2m_max", idx, default=temp_mean)
        rain = value_at(daily, "rain_sum", idx, default=0.0)
        precipitation = value_at(daily, "precipitation_sum", idx, default=rain)
        snow = value_at(daily, "snowfall_sum", idx, default=0.0)
        rows.append(
            {
                "date": day,
                "location_id": location["location_id"],
                "city": location["city"],
                "country_code": location.get("country_code", location.get("country", "")),
                "timezone": location.get("timezone", "auto"),
                "lat": float(location["lat"]),
                "lon": float(location["lon"]),
                "temperature_c": round(float(temp_mean), 2),
                "temperature_min_c": round(float(temp_min), 2),
                "temperature_max_c": round(float(temp_max), 2),
                "rain_mm": round(float(rain), 2),
                "precipitation_mm": round(float(precipitation), 2),
                "snow_cm": round(float(snow), 2),
                "weather_source": "open_meteo_forecast",
                "weather_provider": "Open-Meteo",
                "fetched_at_utc": utc_now(),
            }
        )
    return pd.DataFrame(rows)


def add_weather_flags(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    rows = frame.copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.date.astype(str)
    rows = rows.sort_values(["location_id", "date"]).reset_index(drop=True)
    rows["temp_change_1d_c"] = (
        rows.groupby("location_id")["temperature_c"].diff(1).fillna(0.0).round(2)
    )
    rows["temp_change_3d_c"] = (
        rows.groupby("location_id")["temperature_c"].diff(3).fillna(rows["temp_change_1d_c"]).fillna(0.0).round(2)
    )
    rows["abs_temp_change_3d_c"] = rows["temp_change_3d_c"].abs().round(2)
    rows["cold_snap_flag"] = (
        (rows["temperature_c"] <= -5.0)
        | (rows["temperature_min_c"] <= -8.0)
        | (rows["temp_change_3d_c"] <= -6.0)
        | (rows["snow_cm"] >= 3.0)
    ).astype(int)
    rows["heatwave_flag"] = (
        (rows["temperature_c"] >= 30.0)
        | (rows["temperature_max_c"] >= 33.0)
        | ((rows["temp_change_3d_c"] >= 6.0) & (rows["temperature_c"] >= 23.0))
    ).astype(int)
    rows["weather_spike_flag"] = (
        (rows["abs_temp_change_3d_c"] >= 5.0)
        | (rows["precipitation_mm"] >= 20.0)
        | (rows["snow_cm"] >= 5.0)
    ).astype(int)
    rows["temperature_drop_flag"] = (rows["temp_change_3d_c"] <= -5.0).astype(int)
    rows["temperature_rise_flag"] = (rows["temp_change_3d_c"] >= 5.0).astype(int)
    return rows


def fetch_open_meteo_weather(
    raw_dir: str | Path = RAW_DIR,
    output_path: str | Path | None = None,
    metadata_path: str | Path | None = None,
    forecast_days: int = 16,
    timeout: int = 30,
    sleep_seconds: float = 0.1,
    location_ids: set[str] | None = None,
) -> pd.DataFrame:
    raw_path = Path(raw_dir)
    locations = pd.read_csv(raw_path / "eu_locations.csv")
    if location_ids:
        locations = locations[locations["location_id"].astype(str).isin(location_ids)].copy()
    if locations.empty:
        raise ValueError("No locations available for Open-Meteo fetch.")

    frames: list[pd.DataFrame] = []
    errors: list[dict] = []
    for location in locations.to_dict(orient="records"):
        try:
            frames.append(fetch_location_forecast(pd.Series(location), forecast_days=forecast_days, timeout=timeout))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(
                {
                    "location_id": location.get("location_id"),
                    "city": location.get("city"),
                    "error": str(exc),
                }
            )
        time.sleep(max(0.0, sleep_seconds))

    weather = add_weather_flags(pd.concat(frames, ignore_index=True) if frames else pd.DataFrame())
    output = Path(output_path) if output_path is not None else raw_path / DEFAULT_OUTPUT.name
    metadata = Path(metadata_path) if metadata_path is not None else raw_path / DEFAULT_METADATA.name
    output.parent.mkdir(parents=True, exist_ok=True)

    if not weather.empty:
        weather.to_csv(output, index=False)
    else:
        pd.DataFrame(
            columns=[
                "date",
                "location_id",
                "temperature_c",
                "rain_mm",
                "snow_cm",
                "temp_change_1d_c",
                "temp_change_3d_c",
                "abs_temp_change_3d_c",
                "cold_snap_flag",
                "heatwave_flag",
                "weather_spike_flag",
                "temperature_drop_flag",
                "temperature_rise_flag",
                "weather_source",
            ]
        ).to_csv(output, index=False)

    payload = {
        "generated_at_utc": utc_now(),
        "provider": "Open-Meteo",
        "provider_url": "https://open-meteo.com/",
        "license_note": "Open-Meteo offers free access for non-commercial use; no API key is required.",
        "forecast_days_requested": forecast_days,
        "locations_requested": int(len(locations)),
        "locations_successful": int(weather["location_id"].nunique()) if not weather.empty else 0,
        "rows": int(len(weather)),
        "date_min": weather["date"].min() if not weather.empty else None,
        "date_max": weather["date"].max() if not weather.empty else None,
        "output_file": str(output),
        "errors": errors,
    }
    metadata.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return weather


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch live daily weather forecast from Open-Meteo for project locations.")
    parser.add_argument("--raw-dir", default=str(RAW_DIR), help="Directory containing eu_locations.csv.")
    parser.add_argument("--output", default=None, help="Output CSV path. Default: data/raw/weather_forecast_open_meteo.csv")
    parser.add_argument("--metadata", default=None, help="Output metadata JSON path.")
    parser.add_argument("--forecast-days", type=int, default=16, choices=range(1, 17), metavar="[1-16]")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=0.1)
    parser.add_argument("--location-id", action="append", default=None, help="Optional location_id filter. Can be repeated.")
    args = parser.parse_args()

    frame = fetch_open_meteo_weather(
        raw_dir=args.raw_dir,
        output_path=args.output,
        metadata_path=args.metadata,
        forecast_days=args.forecast_days,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
        location_ids=set(args.location_id) if args.location_id else None,
    )
    print(
        json.dumps(
            {
                "rows": int(len(frame)),
                "locations": int(frame["location_id"].nunique()) if not frame.empty else 0,
                "date_min": frame["date"].min() if not frame.empty else None,
                "date_max": frame["date"].max() if not frame.empty else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
