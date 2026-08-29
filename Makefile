.PHONY: demo run-real ui test lint check download

demo:
	uv run python -m pipeline.run_batch --demo

run-real:
	uv run python -m pipeline.run_batch --dataset data/raw/default/train/0000.parquet --slice 5000

ui:
	uv run streamlit run ui/streamlit_app.py

test:
	uv run pytest -q

lint:
	uv run ruff check .

check: lint test

download:
	uv run python -m data.download
