import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class CloudLoggingFormatter(logging.Formatter):
    """One JSON object per line, which Cloud Logging parses into severity and message."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            # Keeping the traceback in the message lets Error Reporting group the exceptions.
            message += "\n" + self.formatException(record.exc_info)
        return json.dumps({"severity": record.levelname, "message": message, "logger": record.name}, ensure_ascii=False)


def setup_logging() -> None:
    console = logging.StreamHandler(sys.stdout)
    # K_SERVICE is set by Cloud Run.
    console.setFormatter(CloudLoggingFormatter() if os.getenv("K_SERVICE") else logging.Formatter(LOG_FORMAT))
    handlers: list[logging.Handler] = [console]

    if log_file := os.getenv("LOG_FILE"):
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handlers.append(file_handler)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    # The Gemini SDK logs every HTTP request at INFO; keep only warnings and errors.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    # Uvicorn has its own plain-text handlers; route its logs through ours instead.
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.propagate = True
