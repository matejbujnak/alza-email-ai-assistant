"""HTTP entry point for Cloud Run.

Run locally: uv run uvicorn app.main:app --reload
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status

from app import gmail_client
from app.logging_config import setup_logging
from app.processor import process_unread

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Email AI Assistant")


@app.post("/pubsub", status_code=status.HTTP_204_NO_CONTENT)
def handle_gmail_notification() -> None:
    # The notification only says that the inbox changed. All unread emails are processed instead of
    # the referenced change, so a lost or duplicated notification does no harm.
    if failed := process_unread(gmail_client.get_gmail_service()):
        # A non-2xx response makes Pub/Sub redeliver the notification later, which retries the emails.
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"{failed} email(s) failed")


@app.post("/renew-watch", status_code=status.HTTP_204_NO_CONTENT)
def renew_watch() -> None:
    response = gmail_client.watch_inbox(gmail_client.get_gmail_service(), os.environ["PUBSUB_TOPIC"])
    logger.info("Gmail watch renewed until %s (history %s)", response["expiration"], response["historyId"])
