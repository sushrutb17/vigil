# VIGIL

VIGIL turns batches of public NASA Aviation Safety Reporting System (ASRS)
reports into a ranked list of emerging hazards and source-cited investigator
drafts. It drafts and recommends; a human is the only terminal approval gate.

**Live deployment:**
[vigil-ui-715230861973.us-central1.run.app](https://vigil-ui-715230861973.us-central1.run.app)

![VIGIL architecture](docs/architecture.png)

[Explore the interactive architecture](https://vigil-architecture.vercel.app)
or inspect the source in
[`docs/asrs-agent-architecture.mermaid`](docs/asrs-agent-architecture.mermaid).

## What is runnable now

### No credentials required

```bash
uv sync --all-groups
make demo     # end-to-end pipeline on a bundled six-report fixture
make ui       # Streamlit review UI
make check    # Ruff + pytest
```

`make ui` serves `artifacts/demo_run.json` when present—a committed snapshot of
a live run over real ASRS data—so the interface can show genuine model-written
briefs without requiring credentials. It falls back to the bundled fixture when
the snapshot is absent.

### With real data

```bash
make download   # fetch the HF Parquet export and lock the holdout
make run-real   # deterministic stages on the seeded 5,000-report slice
```

`make download` copies the test split once to the read-only
`data/holdout/test.parquet`. Only `eval/holdout_score.py` may read that path, and
the holdout is excluded from Git uploads and every container image.

### With live Gemini agents

Put a Google AI Studio key in the gitignored `.env` file:

```dotenv
GOOGLE_API_KEY=your-key
```

Then run one of these complete live targets:

```bash
make run-live   # print a full live run
make artifact   # run once and save artifacts/demo_run.json for the UI
```

Do not chain `make run-live && make artifact`: each target performs the full
pipeline, so chaining them doubles the model calls. The deterministic stages
stay deterministic in live mode; Gemini writes names, hazard prose, and
escalated-cluster briefs, while clustering and risk scores remain fixed.

## Architecture and safety invariants

- `pipeline/cluster.py` contains no generative-model calls. It uses seeded
  dimensionality reduction and HDBSCAN in a reproducible, single-worker path.
- `config/frozen.yaml` is loaded as immutable runtime policy. No agent can
  retune the escalation threshold.
- `data/holdout/` is locked away from prompt iteration and deployment images.
- `agents/critic.py` enforces both bracketed ACN citation format and an allow-list
  of source ACNs. A citation-shaped hallucination does not pass.
- The Streamlit UI is the terminal gate. VIGIL never sends, files, or
  auto-approves a draft.

The operational agent path uses Google ADK with `gemini-3.7-flash`; embeddings
use `gemini-embedding-2`. Model identifiers were resolved with live Google API
calls on 2026-08-29. Every agent call records the agent name, model, token count,
and latency in Firestore.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design contract and
[`docs/PHASES.md`](docs/PHASES.md) for the live feature-status board.

## Evaluation

ASRS coded fields provide ground truth for extraction, same-event detection, and
cluster quality. Results remain placeholders until the corresponding evaluation
commands have run; no values below are inferred from implementation alone.

| Component | Metric | Baseline | VIGIL result |
|---|---|---:|---:|
| Extractor | Macro-F1 / field accuracy | **TODO** | **TODO** |
| Dedup | Precision / recall | **TODO** | **TODO** |
| Clustering | Purity / adjusted Rand index | **TODO** | **TODO** |
| Clustering | Noise fraction | **TODO** | **TODO** |
| Critic | Seeded uncited-claim catch rate | **TODO** | **TODO** |
| Live run | Reports / clusters / escalations | n/a | **TODO** |

The guard suite also checks for common metric-gaming patterns: too many tiny
clusters, excessive noise, majority-label extraction, and over-merging in dedup.
Evaluation details live in [`docs/EVAL.md`](docs/EVAL.md).

## Cloud deployment

Prerequisites: a Google Cloud project with Cloud Run, Cloud Build, Artifact
Registry, Secret Manager, and Firestore enabled; authenticated `gcloud`; and a
Gemini API key in `.env`.

```bash
gcloud auth login
gcloud config set project your-project-id
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com secretmanager.googleapis.com

export GOOGLE_CLOUD_PROJECT=your-project-id
make deploy
```

Deployment creates two separate Cloud Run surfaces with dedicated identities:

- **`vigil-ui`** is a public Streamlit service. Its service account holds only
  `roles/datastore.user`, allowing Approve/Reject decisions to update the
  `clusters/` and `rejections/` collections. It cannot read the Gemini secret.
- **`vigil-batch`** is a Cloud Run job. Its service account holds Firestore
  access plus `secretmanager.secretAccessor` on the dedicated Gemini-key secret.
  The deployed job uses the bundled fixture because `data/raw/` is deliberately
  excluded from the image.

`.gcloudignore` and `.dockerignore` exclude `.env`, `.venv`, `data/raw/`, and
`data/holdout/`. The root-level Dockerfile is intentional: `gcloud run deploy
--source .` only auto-detects a Dockerfile at the build-context root. See
[`infra/README.md`](infra/README.md) for the rationale.

## Data credit and disclosure

VIGIL uses public NASA ASRS data packaged by the Hugging Face dataset
`elihoole/asrs-aviation-reports` (Apache-2.0 packaging). Historical reports are
shown as a replay, never represented as a live feed. The project was built with
Google ADK, Gemini, Google Cloud, open-source Python libraries, and AI coding
assistance from Claude Code and Codex.
