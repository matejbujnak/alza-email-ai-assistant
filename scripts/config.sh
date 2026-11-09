# Shared settings for the deployment scripts. Override any of them with an environment variable.
PROJECT="${PROJECT:-alza-email-assistant-514009}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-alza-email-assistant}"
TOPIC="${TOPIC:-gmail-notifications}"
SUBSCRIPTION="${SUBSCRIPTION:-gmail-to-cloud-run}"

RUNTIME_SA="alza-bot@${PROJECT}.iam.gserviceaccount.com"
INVOKER_SA="alza-bot-invoker@${PROJECT}.iam.gserviceaccount.com"
BUILDER_SA="alza-bot-builder@${PROJECT}.iam.gserviceaccount.com"
