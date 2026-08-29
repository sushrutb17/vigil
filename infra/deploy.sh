#!/usr/bin/env bash
# Deploy the VIGIL UI (Cloud Run service) and batch pipeline (Cloud Run job).
#
# Prerequisites:
#   gcloud auth login && gcloud config set project <project>
#   export GOOGLE_CLOUD_PROJECT=vigil-hackathon
#   export GOOGLE_API_KEY=...        # same key used locally, from .env
#
# What gets uploaded is controlled by .gcloudignore, which deliberately excludes
# .venv, data/raw, and data/holdout. The locked holdout must never ship inside a
# container image (guardrail #3).
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT before deployment}"
: "${GOOGLE_API_KEY:?Set GOOGLE_API_KEY before deployment (see .env)}"
GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION:-us-central1}"

echo "==> Deploying UI service (vigil-ui) to $GOOGLE_CLOUD_REGION"
# The UI serves the committed artifacts/demo_run.json snapshot, so it needs no
# model credentials to render and costs nothing per pageview.
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
#
# GOOGLE_API_KEY is passed as an env var rather than through Secret Manager:
# a deliberate simplification for a time-boxed hackathon build (BUILD_PLAN's
# anti-stall rule on auth). Secret Manager is the right production choice.
gcloud run jobs deploy vigil-batch \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_REGION" \
  --source . \
  --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY,GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT" \
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
echo "  gcloud run jobs execute vigil-batch --project $GOOGLE_CLOUD_PROJECT --region $GOOGLE_CLOUD_REGION"
