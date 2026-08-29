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
# Each workload runs as its own minimally-privileged service account rather than
# the default compute SA (which usually holds primitive Editor project-wide).
# If a previous deploy of this script bound secretAccessor to the default
# compute SA, revoke it:
#   gcloud secrets remove-iam-policy-binding gemini-api-key \
#     --member "serviceAccount:$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" \
#       --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
#     --role roles/secretmanager.secretAccessor
#
# What gets uploaded is controlled by .gcloudignore (and .dockerignore for local
# docker builds), which deliberately exclude .env, .venv, data/raw, and
# data/holdout. The locked holdout must never ship inside an image (guardrail #3).
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT before deployment}"
: "${GOOGLE_API_KEY:?Set GOOGLE_API_KEY before deployment (see .env)}"
GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
SECRET_NAME="gemini-api-key"

# Two dedicated runtime identities instead of the default compute service
# account. That default typically carries primitive Editor on the whole project,
# which would make the public --allow-unauthenticated UI a project editor: any
# RCE or SSRF in Streamlit or app code would hand an attacker editor credentials
# from the metadata server. Splitting them also means "the UI cannot read the
# API key" is enforced by IAM rather than by merely not mounting it.
#
#   vigil-ui-run    — roles/datastore.user only (added 2026-08-29 when the
#                     Approve/Reject buttons started writing decisions to
#                     Firestore's clusters/ and rejections/ collections — see
#                     pipeline/store.py TriageStore.set_cluster_status /
#                     put_rejection). No secretAccessor: the UI never needs the
#                     Gemini key, since it serves the committed
#                     artifacts/demo_run.json snapshot rather than calling the
#                     model itself.
#   vigil-batch-run — secretAccessor on this one secret, plus Firestore access.
UI_SA="vigil-ui-run@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
BATCH_SA="vigil-batch-run@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

ensure_service_account() {
  local account_id="$1" display_name="$2"
  if ! gcloud iam service-accounts describe \
      "${account_id}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
      --project "$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$account_id" \
      --project "$GOOGLE_CLOUD_PROJECT" --display-name "$display_name"
  fi
}

echo "==> Ensuring dedicated runtime service accounts"
ensure_service_account vigil-ui-run "VIGIL UI (no privileges)"
ensure_service_account vigil-batch-run "VIGIL batch job"

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

# Least privilege: accessor on this one secret, granted only to the batch
# identity. The UI identity is deliberately never bound here.
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --member "serviceAccount:${BATCH_SA}" \
  --role roles/secretmanager.secretAccessor \
  --condition=None >/dev/null

# Firestore read/write for the batch job.
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member "serviceAccount:${BATCH_SA}" \
  --role roles/datastore.user \
  --condition=None >/dev/null

# Firestore read/write for the UI too, scoped to datastore.user only (no
# secretAccessor, no broader role) — the human-gate Approve/Reject buttons
# write cluster status + rejections directly from the UI process.
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member "serviceAccount:${UI_SA}" \
  --role roles/datastore.user \
  --condition=None >/dev/null

echo "==> Deploying UI service (vigil-ui) to $GOOGLE_CLOUD_REGION"
# Runs as vigil-ui-run: datastore.user only, no secretAccessor. The UI serves
# the committed artifacts/demo_run.json snapshot for reads (no model calls,
# no per-pageview cost) but needs GOOGLE_CLOUD_PROJECT + Firestore access so
# Approve/Reject persist real decisions into the same project the batch job
# wrote clusters/escalations to (ui.streamlit_app._get_store selects
# FirestoreStore whenever this env var is present).
gcloud run deploy vigil-ui \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_REGION" \
  --source . \
  --service-account "$UI_SA" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT" \
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
  --service-account "$BATCH_SA" \
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
