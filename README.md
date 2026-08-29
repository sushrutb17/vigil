# VIGIL

VIGIL turns a batch of public NASA ASRS safety reports into a ranked list of
emerging hazards and source-cited investigator drafts. It drafts and recommends;
a human is the only terminal approval gate.

**Live:** https://vigil-ui-715230861973.us-central1.run.app

## What is runnable now

### No credentials required

```bash
uv sync --all-groups
make demo     # end-to-end pipeline on a bundled six-report fixture
make ui       # Streamlit review UI
make check    # ruff + pytest
```

`make ui` serves `artifacts/demo_run.json` when present — a committed snapshot of
a real live run over real ASRS data (23 hazard clusters, 4 escalated, 816 reports
triaged), so the UI shows genuine model-written briefs without any credentials.
It falls back to the bundled fixture if that file is absent.

### With real data

```bash
make download   # HF Parquet export; locks data/holdout/test.parquet read-only
make run-real   # 5,000-report seeded slice, deterministic stages only
```

`make download` fetches only the Hugging Face Parquet export and makes the test
split a one-time, read-only `data/holdout/test.parquet` copy. Only
`eval/holdout_score.py` may read that path, and it is excluded from every
container image.

### With live Gemini agents

Put a Google AI Studio key in `.env` (gitignored) as `GOOGLE_API_KEY=...`, then:

```bash
set -a; source .env; set +a
make run-live   # adds a live Analyst call per cluster, plus the parallel
                # Coordinator (Precedent ∥ Risk ∥ Brief Writer) and Critic
                # for every escalated cluster
make artifact   # same run, saved to artifacts/demo_run.json for the UI
```

Deterministic stages stay deterministic in live mode: clustering and risk scoring
are byte-identical with and without `--live`. Only naming, prose, and brief
drafting come from the model.

## Architecture and safety invariants

`pipeline/cluster.py` has no generative model calls: it clusters embeddings with
HDBSCAN only, in a reproducible single-worker configuration. The risk policy in
`config/frozen.yaml` is loaded as immutable data at runtime; agents cannot retune
the escalation threshold. The deterministic citation gate in `agents/critic.py`
removes every factual claim missing a bracketed ACN citation.

The live ADK graph is defined in `agents/definitions.py`, using the verified Flash
model ID `gemini-3.7-flash`; batch embedding uses `gemini-embedding-2`. Both IDs
were verified in Google AI model documentation on 2026-08-21. No credentials are
included or required for the local demo.

**Current build status, phase by phase:** [`docs/PHASES.md`](docs/PHASES.md) — read this first if you're picking the project up mid-stream.

For detailed design, evaluation, delivery plan, and recording plan, see
[the project docs](docs/ARCHITECTURE.md).

## Cloud deployment

```bash
gcloud auth login
gcloud config set project your-project
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com secretmanager.googleapis.com

set -a; source .env; set +a
export GOOGLE_CLOUD_PROJECT=your-project
make deploy
```

This deploys two separate Cloud Run surfaces, each with its own least-privilege
service account rather than the default compute identity:

- **`vigil-ui`** (public, `--allow-unauthenticated`) — holds **no IAM roles at
  all**. It only serves the committed `artifacts/demo_run.json` snapshot: no
  model calls, no Firestore, no secrets.
- **`vigil-batch`** (Cloud Run job) — holds `secretmanager.secretAccessor` on a
  dedicated `gemini-api-key` secret (created by `deploy.sh`, never passed as a
  plain env var) and `roles/datastore.user`. Runs the full pipeline with
  `--live --firestore`, exercising all three mandatory stack components in one
  execution.

`.gcloudignore` and `.dockerignore` both exclude `.env`, `.venv`, `data/raw`, and
`data/holdout` — the locked holdout must never reach a container image. See
[`infra/README.md`](infra/README.md) for why the Dockerfile lives at the repo
root instead of `infra/`.

## Data credit

VIGIL uses the public NASA Aviation Safety Reporting System corpus as packaged
by Hugging Face dataset `elihoole/asrs-aviation-reports` (Apache-2.0 packaging).
The historical data is demonstrated as a replay, never represented as a live feed.
