"""Generate a reply for a hand-written email without touching Gmail.

Usage:
    uv run python -m app.try_reply --body "Ahoj, čo je HDR?" [--subject "Otázka"]
    uv run python -m app.try_reply --body "Čo je na faktúre?" --attach faktura.pdf --attach foto.jpg
"""

import argparse
import mimetypes
import time
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

from app.filters import skip_reason
from app.gmail_client import parse_email
from app.llm import generate_reply
from app.logging_config import setup_logging


def build_message(sender: str, subject: str, body: str, attachments: list[Path]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments:
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        maintype, subtype = mime_type.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--body", required=True)
    parser.add_argument("--subject", default="")
    parser.add_argument("--sender", default="customer@example.com")
    parser.add_argument("--attach", type=Path, action="append", default=[], help="file to attach (repeatable)")
    args = parser.parse_args()

    load_dotenv()
    setup_logging()

    msg = build_message(args.sender, args.subject, args.body, args.attach)
    email = parse_email(msg.as_bytes(), gmail_id="local", thread_id="local")

    if reason := skip_reason(email, own_address="bot@example.com"):
        print(f"Skipped: {reason}")
        return

    start = time.perf_counter()
    reply = generate_reply(email)
    print(f"\n{reply}\n\n--- generated in {time.perf_counter() - start:.1f} s")


if __name__ == "__main__":
    main()
