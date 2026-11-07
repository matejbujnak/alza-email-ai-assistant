import logging

from dotenv import load_dotenv

from app import gmail_client
from app.filters import skip_reason
from app.llm import generate_reply
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)


def process_message(service, message_id: str, own_address: str) -> None:
    email = gmail_client.get_email(service, message_id)

    if reason := skip_reason(email, own_address):
        logger.info("Skipping %s from %s: %s", email.id, email.sender, reason)
    else:
        reply = generate_reply(email)
        gmail_client.send_reply(service, email, reply)
        logger.info("Replied to %s from %s", email.id, email.sender)

    gmail_client.mark_as_read(service, email.id)


def process_unread(service) -> None:
    own_address = gmail_client.get_own_address(service)

    for message_id in gmail_client.list_unread_ids(service):
        try:
            process_message(service, message_id, own_address)
        except Exception:
            # Leave the email unread so it is retried on the next run.
            logger.exception("Failed to process %s", message_id)


if __name__ == "__main__":
    load_dotenv()
    setup_logging()
    process_unread(gmail_client.get_gmail_service())
