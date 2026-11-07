from app.gmail_client import IncomingEmail

NO_REPLY_MARKERS = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster")
BULK_PRECEDENCE = {"bulk", "list", "junk", "auto_reply"}


def skip_reason(email: IncomingEmail, bot_address: str) -> str | None:
    sender = email.sender.lower()
    headers = email.mime

    if sender == bot_address.lower():
        return "sent by the bot itself"
    if any(marker in sender for marker in NO_REPLY_MARKERS):
        return "no-reply sender"
    if headers.get("Auto-Submitted", "no").lower() != "no":
        return "auto-submitted message"
    if headers.get("Precedence", "").lower() in BULK_PRECEDENCE:
        return "bulk/list precedence"
    if headers.get("List-Id") or headers.get("List-Unsubscribe"):
        return "mailing list"
    return None
