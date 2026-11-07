"""Generate a reply for a hand-written email without touching Gmail.

Usage:
    uv run python -m app.try_reply --body "Ahoj, čo je HDR?" [--subject "Otázka"]
"""

import argparse
import time
from email.message import EmailMessage

from dotenv import load_dotenv

from app.filters import skip_reason
from app.gmail_client import parse_email
from app.llm import generate_reply
from app.logging_config import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--body", required=True)
    parser.add_argument("--subject", default="")
    parser.add_argument("--sender", default="customer@example.com")
    args = parser.parse_args()

    load_dotenv()
    setup_logging()

    msg = EmailMessage()
    msg["From"] = args.sender
    msg["Subject"] = args.subject
    msg.set_content(args.body)
    email = parse_email(msg.as_bytes(), gmail_id="local", thread_id="local")

    if reason := skip_reason(email, bot_address="bot@example.com"):
        print(f"Skipped: {reason}")
        return

    start = time.perf_counter()
    reply = generate_reply(email)
    print(f"\n{reply}\n\n--- generated in {time.perf_counter() - start:.1f} s")


if __name__ == "__main__":
    main()
