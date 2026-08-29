.PHONY: demo run-real run-live artifact ui test lint check download deploy

demo:
	uv run python -m pipeline.run_batch --demo

run-real:
	uv run python -m pipeline.run_batch --dataset data/raw/default/train/0000.parquet --slice 5000

run-live:
	uv run python -m pipeline.run_batch --dataset data/raw/default/train/0000.parquet --slice 5000 --live

# Regenerates the snapshot the deployed Cloud Run UI serves. Needs GOOGLE_API_KEY.
artifact:
	uv run python -m pipeline.run_batch --dataset data/raw/default/train/0000.parquet \
		--slice 5000 --live --output artifacts/demo_run.json > /dev/null
	@echo "Wrote artifacts/demo_run.json"

deploy:
	./infra/deploy.sh

ui:
	uv run streamlit run ui/streamlit_app.py

test:
	uv run pytest -q

lint:
	uv run ruff check .

check: lint test

download:
	uv run python -m data.download
