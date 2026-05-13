from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(os.getenv("BASE_DIR", ".")).resolve()
DATA_RAW_DIR = Path(os.getenv("DATA_RAW_DIR", BASE_DIR / "data" / "raw")).resolve()
DATA_PROCESSED_DIR = Path(os.getenv("DATA_PROCESSED_DIR", BASE_DIR / "data" / "processed")).resolve()
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models")).resolve()
DEFAULT_FORECAST_HORIZON = int(os.getenv("DEFAULT_FORECAST_HORIZON", "30"))
API_TITLE = os.getenv("API_TITLE", "Stock Optimizer ML EU API")
API_VERSION = os.getenv("API_VERSION", "2.0.0")
