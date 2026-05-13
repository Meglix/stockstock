import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.cluster import train_cluster_model
from ml.data_generator import generate_dataset
from ml.decision_layer import generate_decision_layer
from ml.forecast import run_forecast
from ml.recommend import generate_recommendations
from ml.train import train_forecast_model
from generate_model_charts import main as generate_model_charts
from weather_int import main as generate_sales_intelligence_plots


def main() -> None:
    parser = argparse.ArgumentParser(description="Ruleaza pipeline-ul complet de stock optimizer.")
    parser.add_argument(
        "--skip-generate-dataset",
        action="store_true",
        help="Foloseste CSV-urile existente din data/raw in loc sa le suprascrie.",
    )
    args = parser.parse_args()

    if not args.skip_generate_dataset:
        print(generate_dataset())
    else:
        print({"raw_dataset": "kept_existing_data_raw"})
    print(train_forecast_model()["forecast_model_metrics"])
    print(train_cluster_model())
    forecast = run_forecast(horizon=30)
    print({"forecast_rows": len(forecast)})
    rec = generate_recommendations(horizon=30)
    print({key: len(value) for key, value in rec.items()})
    generate_sales_intelligence_plots()
    generate_model_charts()
    print(generate_decision_layer(horizon=21))


if __name__ == "__main__":
    main()
