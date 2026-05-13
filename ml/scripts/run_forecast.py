import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.forecast import run_forecast

if __name__ == "__main__":
    df = run_forecast(horizon=30)
    print({"rows": len(df), "min_date": df["forecast_date"].min(), "max_date": df["forecast_date"].max()})
