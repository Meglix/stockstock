import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.forecast import run_forecast

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate demand forecast.")
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument(
        "--start-date",
        default=None,
        help="Optional forecast start date in YYYY-MM-DD format. Useful for live Open-Meteo demo forecasts.",
    )
    args = parser.parse_args()
    df = run_forecast(horizon=args.horizon, start_date=args.start_date)
    print({"rows": len(df), "min_date": df["forecast_date"].min(), "max_date": df["forecast_date"].max()})
