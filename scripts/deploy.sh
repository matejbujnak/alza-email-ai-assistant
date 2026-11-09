#!/usr/bin/env bash
# Build the image from the current directory and deploy a new Cloud Run revision.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --build-service-account "projects/${PROJECT}/serviceAccounts/${BUILDER_SA}" \
  --service-account "$RUNTIME_SA" \
  --no-allow-unauthenticated \
  --set-secrets "/secrets/token.json=gmail-token:latest,GEMINI_API_KEY=gemini-api-key:latest" \
  --set-env-vars "GMAIL_TOKEN_FILE=/secrets/token.json,PUBSUB_TOPIC=projects/${PROJECT}/topics/${TOPIC}" \
  --memory 1Gi \
  --max-instances 3 \
  --cpu-boost
