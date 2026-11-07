from email.message import EmailMessage

import pytest

from app.gmail_client import IncomingEmail, parse_email


def build_email(
    body: str = "Hello",
    subject: str = "Question",
    sender: str = "Jane Doe <jane@example.com>",
    **headers: str,
) -> IncomingEmail:
    msg = EmailMessage()
    msg["From"] = sender
    msg["Subject"] = subject
    msg["Message-ID"] = "<original@example.com>"
    for name, value in headers.items():
        msg[name.replace("_", "-")] = value
    msg.set_content(body)
    return parse_email(msg.as_bytes(), gmail_id="gmail-1", thread_id="thread-1")


@pytest.fixture
def make_email():
    return build_email
