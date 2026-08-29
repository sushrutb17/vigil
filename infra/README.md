# infra/

`deploy.sh` — deploys the Streamlit UI as a Cloud Run **service** and the batch
pipeline as a Cloud Run **job**. See the header comment in that script for
prerequisites and what each deployment does.

## Why the Dockerfile lives at the repo root, not here

`docs/ARCHITECTURE.md` and `CLAUDE.md` place the Dockerfile in `infra/`, but
`gcloud run deploy --source .` only detects a Dockerfile at the **root** of the
build context. With the Dockerfile in `infra/`, gcloud silently falls back to
buildpack autodetection instead — which produces a different (and for a
Streamlit entrypoint, wrong) image rather than an error.

The alternatives that would preserve the documented layout — a `cloudbuild.yaml`
running `docker build -f infra/Dockerfile`, plus manual Artifact Registry repo
creation and image tagging — add moving parts and a second failure surface to a
step that has to work on the first attempt in a time-boxed build. Root Dockerfile
is also simply the convention the tooling expects.

## What is excluded from the image

`.gcloudignore` controls the upload. It deliberately excludes `.venv` (594MB),
`data/raw` (60MB), and `data/holdout`. That last one is a guardrail, not an
optimization: per guardrail #3 the locked holdout is readable only by
`eval/holdout_score.py`, which runs locally — it must never be baked into a
deployed container image.
