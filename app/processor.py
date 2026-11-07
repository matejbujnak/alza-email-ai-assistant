import logging

from app import gmail_client
from app.filters import skip_reason

logger = logging.getLogger(__name__)

PLACEHOLDER_REPLY = "Thank you for your email. This is an automated reply from the AI assistant."


def process_unread(service) -> None:
    bot_address = gmail_client.get_bot_address(service)

    for message_id in gmail_client.list_unread_ids(service):
        email = gmail_client.get_email(service, message_id)

        if reason := skip_reason(email, bot_address):
            logger.info("Skipping %s from %s: %s", email.id, email.sender, reason)
        else:
            gmail_client.send_reply(service, email, PLACEHOLDER_REPLY)
            logger.info("Replied to %s from %s", email.id, email.sender)

        gmail_client.mark_as_read(service, email.id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    process_unread(gmail_client.get_gmail_service())
