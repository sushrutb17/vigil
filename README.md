# VIGIL

VIGIL turns a batch of public NASA ASRS safety reports into a ranked list of
emerging hazards and source-cited investigator drafts. It drafts and recommends;
a human is the only terminal approval gate.

## What is runnable now

The repository includes a complete deterministic local demo: schema normalization,
TF-IDF embedding fallback, seeded HDBSCAN clustering, frozen risk routing,
idempotency, ACN citation stripping, evaluation guards, and a Streamlit review UI.

```bash
uv sync --all-groups
make demo
make ui
make check
```

The demo operates only on a tiny bundled fixture. To fetch the approved public
dataset later, run `make download`. It downloads only the Hugging Face Parquet
export and makes the test split a one-time, read-only `data/holdout/test.parquet`
copy. Only `eval/holdout_score.py` is allowed to read that path.

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

For detailed design, evaluation, delivery plan, and recording plan, see
[the project docs](docs/ARCHITECTURE.md).

## Cloud deployment (credential-dependent)

After creating a Google Cloud project, enabling Cloud Run and Firestore, and
authenticating `gcloud`, deploy with:

```bash
GOOGLE_CLOUD_PROJECT=your-project infra/deploy.sh
```

The batch job and UI remain separate Cloud Run surfaces. Before a live run, set
either Gemini API-key authentication for local ADK development or Vertex AI
credentials for Cloud Run, then validate the model ID again in the official
Google documentation.

## Data credit

VIGIL uses the public NASA Aviation Safety Reporting System corpus as packaged
by Hugging Face dataset `elihoole/asrs-aviation-reports` (Apache-2.0 packaging).
The historical data is demonstrated as a replay, never represented as a live feed.
