#!/usr/bin/env bash
# Deploy the VIGIL UI (Cloud Run service) and batch pipeline (Cloud Run job).
#
# Prerequisites:
#   gcloud auth login && gcloud config set project <project>
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
#       artifactregistry.googleapis.com secretmanager.googleapis.com
#   export GOOGLE_CLOUD_PROJECT=vigil-hackathon
#   export GOOGLE_API_KEY=...        # same key used locally, from .env
#
# The API key is stored in Secret Manager and mounted by reference, never passed
# with --set-env-vars: Cloud Run env vars are readable by anyone with viewer
# access on the project and show up in deployment history and `describe` output.
#
# What gets uploaded is controlled by .gcloudignore (and .dockerignore for local
# docker builds), which deliberately exclude .env, .venv, data/raw, and
# data/holdout. The locked holdout must never ship inside an image (guardrail #3).
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT before deployment}"
: "${GOOGLE_API_KEY:?Set GOOGLE_API_KEY before deployment (see .env)}"
GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
SECRET_NAME="gemini-api-key"

PROJECT_NUMBER="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" \
  --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "==> Storing the Gemini API key in Secret Manager ($SECRET_NAME)"
# printf without a trailing newline: a stray \n inside the secret payload would
# be sent as part of the key and every model call would fail to authenticate.
if gcloud secrets describe "$SECRET_NAME" --project "$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
  printf '%s' "$GOOGLE_API_KEY" | gcloud secrets versions add "$SECRET_NAME" \
    --project "$GOOGLE_CLOUD_PROJECT" --data-file=-
else
  printf '%s' "$GOOGLE_API_KEY" | gcloud secrets create "$SECRET_NAME" \
    --project "$GOOGLE_CLOUD_PROJECT" --replication-policy=automatic --data-file=-
fi

# Least privilege: accessor on this one secret only, not project-wide.
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role roles/secretmanager.secretAccessor \
  --condition=None >/dev/null

echo "==> Deploying UI service (vigil-ui) to $GOOGLE_CLOUD_REGION"
# The UI serves the committed artifacts/demo_run.json snapshot, so it needs no
# model credentials at all — the API key is deliberately not mounted here.
gcloud run deploy vigil-ui \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_REGION" \
  --source . \
  --min-instances 0 \
  --memory 1Gi \
  --allow-unauthenticated

echo "==> Deploying batch job (vigil-batch)"
# Runs the full pipeline with live Gemini agents and Firestore persistence, so
# one execution exercises all three mandatory stack components: ADK/Gemini,
# Cloud Run, and Firestore. Uses the bundled fixture because data/raw is
# (correctly) excluded from the image; the real-data run is the local/video path.
gcloud run jobs deploy vigil-batch \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_REGION" \
  --source . \
  --set-secrets "GOOGLE_API_KEY=${SECRET_NAME}:latest" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT" \
  --max-retries 1 \
  --task-timeout 15m \
  --command python \
  --args -m,pipeline.run_batch,--demo,--live,--firestore

echo
echo "==> Deployed. UI URL:"
gcloud run services describe vigil-ui \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_REGION" \
  --format 'value(status.url)'
echo
echo "Run the batch job with:"
echo "  gcloud run jobs execute vigil-batch --project $GOOGLE_CLOUD_PROJECT --region $GOOGLE_CLOUD_REGION --wait"
