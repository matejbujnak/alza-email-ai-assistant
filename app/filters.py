import re

from app.gmail_client import IncomingEmail

NO_REPLY_MARKERS = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster")
BULK_PRECEDENCE = {"bulk", "list", "junk", "auto_reply"}

TRUSTED_AUTHSERV_ID = "mx.google.com"
AUTH_RESULT = re.compile(r"\b(dmarc|spf|dkim)=(\w+)", re.IGNORECASE)


def authentication_failure(email: IncomingEmail) -> str | None:
    # Only the topmost header is trusted: Gmail prepends its own verdict, while
    # anything below it could have been written by the sender.
    header = email.mime.get("Authentication-Results")
    if header is None:
        return None

    authserv_id, _, results = str(header).partition(";")
    if authserv_id.strip().lower() != TRUSTED_AUTHSERV_ID:
        return "untrusted authentication results"

    verdicts: dict[str, str] = {}
    for method, result in AUTH_RESULT.findall(results):
        verdicts.setdefault(method.lower(), result.lower())

    if verdicts.get("dmarc") == "fail":
        return "DMARC failed"
    if "pass" not in (verdicts.get("spf"), verdicts.get("dkim")):
        return "neither SPF nor DKIM passed"
    return None


def skip_reason(email: IncomingEmail, own_address: str) -> str | None:
    headers = email.mime

    if email.sender.lower() == own_address.lower():
        return "sent by this inbox"
    if failure := authentication_failure(email):
        return f"sender not authenticated: {failure}"
    # Check where the reply would go, not the sender: contact forms send from
    # noreply@ but put the customer in Reply-To.
    if any(marker in email.reply_to.lower() for marker in NO_REPLY_MARKERS):
        return "no-reply address"
    if headers.get("Auto-Submitted", "no").lower() != "no":
        return "auto-submitted message"
    if headers.get("Precedence", "").lower() in BULK_PRECEDENCE:
        return "bulk/list precedence"
    if headers.get("List-Id") or headers.get("List-Unsubscribe"):
        return "mailing list"
    return None
