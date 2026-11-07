import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file := os.getenv("LOG_FILE"):
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"))

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers, force=True)
    # The Gemini SDK logs every HTTP request at INFO; keep only warnings and errors.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
