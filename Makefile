.PHONY: demo ui test lint check download

demo:
	uv run python -m pipeline.run_batch --demo

ui:
	uv run streamlit run ui/streamlit_app.py

test:
	uv run pytest -q

lint:
	uv run ruff check .

check: lint test

download:
	uv run python -m data.download
