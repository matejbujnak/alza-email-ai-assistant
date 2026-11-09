import logging
from datetime import timedelta

from dotenv import load_dotenv

from app import claims, gmail_client
from app.claims import Claim
from app.filters import skip_reason
from app.llm import generate_reply
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Older emails are ignored. Must stay below claims.RETENTION: once a record expires, an old email
# marked unread again would otherwise be answered a second time.
MAX_EMAIL_AGE = timedelta(days=7)


def process_message(service, message_id: str, own_address: str) -> None:
    match claims.claim(message_id):
        case Claim.IN_PROGRESS:
            logger.info("Skipping %s: being processed by another instance", message_id)
            return
        case Claim.DONE:
            # Already answered; it is unread only because marking it as read failed or a person
            # marked it unread. Mark it read so it doesn't keep showing up in the unread list.
            logger.info("Skipping %s: already handled", message_id)
            gmail_client.mark_as_read(service, message_id)
            return

    try:
        email = gmail_client.get_email(service, message_id)
        if reason := skip_reason(email, own_address):
            logger.info("Skipping %s from %s: %s", email.id, email.sender, reason)
        else:
            reply = generate_reply(email)
            gmail_client.send_reply(service, email, reply)
            logger.info("Replied to %s from %s", email.id, email.sender)
    except Exception:
        # Nothing was sent, so let the next run try again.
        claims.release(message_id)
        raise

    # Recorded before marking as read: if that fails, the email is not answered twice.
    claims.mark_done(message_id)
    gmail_client.mark_as_read(service, message_id)


def process_unread(service) -> None:
    own_address = gmail_client.get_own_address(service)

    for message_id in gmail_client.list_unread_ids(service, newer_than_days=MAX_EMAIL_AGE.days):
        try:
            process_message(service, message_id, own_address)
        except Exception:
            # Leave the email unread so it is retried on the next run.
            logger.exception("Failed to process %s", message_id)


if __name__ == "__main__":
    load_dotenv()
    setup_logging()
    process_unread(gmail_client.get_gmail_service())
