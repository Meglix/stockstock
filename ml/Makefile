.PHONY: install data train cluster forecast weather-live recommend decision build-all api docker-build docker-up

install:
	python -m pip install -r requirements.txt

data:
	PYTHONPATH=. python scripts/generate_dataset.py

train:
	PYTHONPATH=. python scripts/train_forecast_model.py

cluster:
	PYTHONPATH=. python scripts/train_cluster_model.py

forecast:
	PYTHONPATH=. python scripts/run_forecast.py

weather-live:
	PYTHONPATH=. python scripts/fetch_open_meteo_weather.py

recommend:
	PYTHONPATH=. python scripts/generate_recommendations.py

decision:
	PYTHONPATH=. python scripts/build_decision_layer.py

build-all:
	PYTHONPATH=. python scripts/build_all.py

api:
	PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t stock-optimizer-ml-eu .

docker-up:
	docker compose up --build
