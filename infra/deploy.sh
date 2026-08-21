#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT before deployment}"
: "${GOOGLE_CLOUD_REGION:=us-central1}"

gcloud run deploy vigil-ui \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_REGION" \
  --source . \
  --min-instances 0 \
  --allow-unauthenticated

gcloud run jobs deploy vigil-batch \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_REGION" \
  --source . \
  --command python \
  --args -m,pipeline.run_batch,--demo
