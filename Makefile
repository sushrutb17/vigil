.PHONY: demo run-real run-live artifact ui test lint check download deploy require-key

# Load .env when it exists so the --live targets work without remembering to
# `set -a; source .env; set +a` first. Forgetting it does not fail cleanly: ADK
# raises inside the first Analyst call, once per cluster, and buries the one
# useful line ("No API key was provided") under several hundred lines of async
# traceback. .env is gitignored and holds a single unquoted KEY=value line.
ifneq (,$(wildcard .env))
include .env
export
endif

# Fail in one line rather than mid-run, after the deterministic stages have
# already spent time clustering 5,000 reports.
require-key:
	@if [ -z "$$GOOGLE_API_KEY" ]; then \
		echo "GOOGLE_API_KEY is not set and no .env provides it."; \
		echo "Put 'GOOGLE_API_KEY=...' in .env (gitignored), or export it, then retry."; \
		exit 1; \
	fi

demo:
	uv run python -m pipeline.run_batch --demo

run-real:
	uv run python -m pipeline.run_batch --dataset data/raw/default/train/0000.parquet --slice 5000

run-live: require-key
	uv run python -m pipeline.run_batch --dataset data/raw/default/train/0000.parquet --slice 5000 --live

# Regenerates the snapshot the deployed Cloud Run UI serves. Needs GOOGLE_API_KEY.
# This is a COMPLETE live run, identical to run-live except that it writes the
# result to a file instead of stdout. Do not chain `run-live && artifact`: that
# runs the whole pipeline twice, roughly 78 live Gemini calls instead of 39, for
# one snapshot. Use this target on its own.
artifact: require-key
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
