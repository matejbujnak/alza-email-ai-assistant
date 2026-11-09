#!/usr/bin/env bash
# One-time setup of a new Google Cloud project. Prerequisites:
#   - the project exists and has a billing account linked
#   - the Gmail API and OAuth consent screen are configured, and `token.json` exists
#     (uv run python -m app.gmail_client login)
#   - GEMINI_API_KEY is set in .env
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh
gcloud config set project "$PROJECT"

echo "== APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  pubsub.googleapis.com firestore.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com

echo "== Firestore (records expire via TTL on expire_at)"
gcloud firestore databases create --location="$REGION"
gcloud firestore fields ttls update expire_at --collection-group=processed_emails --enable-ttl --async

echo "== Secrets"
gcloud secrets create gmail-token --replication-policy=user-managed --locations="$REGION" --data-file=token.json
uv run python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['GEMINI_API_KEY'], end='')" \
  | gcloud secrets create gemini-api-key --replication-policy=user-managed --locations="$REGION" --data-file=-

echo "== Service accounts"
gcloud iam service-accounts create alza-bot --display-name="Email AI Assistant runtime"
gcloud iam service-accounts create alza-bot-invoker --display-name="Invokes Email AI Assistant (Pub/Sub, Scheduler)"
gcloud iam service-accounts create alza-bot-builder --display-name="Builds Email AI Assistant images"

for secret in gmail-token gemini-api-key; do
  gcloud secrets add-iam-policy-binding "$secret" --member="serviceAccount:${RUNTIME_SA}" \
    --role=roles/secretmanager.secretAccessor
done
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${RUNTIME_SA}" \
  --role=roles/datastore.user --condition=None
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${BUILDER_SA}" \
  --role=roles/run.builder --condition=None

echo "== Cloud Run"
scripts/deploy.sh
URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
gcloud run services add-iam-policy-binding "$SERVICE" --region "$REGION" \
  --member="serviceAccount:${INVOKER_SA}" --role=roles/run.invoker

echo "== Pub/Sub (Gmail publishes, the push subscription calls the service)"
gcloud pubsub topics create "$TOPIC"
gcloud pubsub topics add-iam-policy-binding "$TOPIC" \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" --role=roles/pubsub.publisher
gcloud pubsub subscriptions create "$SUBSCRIPTION" --topic "$TOPIC" \
  --push-endpoint="${URL}/pubsub" --push-auth-service-account="$INVOKER_SA" \
  --ack-deadline=300 --min-retry-delay=10s --max-retry-delay=600s --message-retention-duration=1h

echo "== Scheduler (daily watch renewal, 5-minute fallback for missed notifications)"
for job in "renew-gmail-watch|0 6 * * *|/renew-watch" "process-unread-fallback|*/5 * * * *|/pubsub"; do
  IFS='|' read -r name schedule path <<< "$job"
  gcloud scheduler jobs create http "$name" --location "$REGION" \
    --schedule "$schedule" --time-zone "Europe/Bratislava" --http-method POST --uri "${URL}${path}" \
    --oidc-service-account-email "$INVOKER_SA" --oidc-token-audience "$URL"
done

echo "== Start the Gmail watch"
gcloud scheduler jobs run renew-gmail-watch --location "$REGION"
echo "Done: $URL"
