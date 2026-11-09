import json
import logging

from app.logging_config import CloudLoggingFormatter


def record(level: int, message: str, exc_info=None) -> logging.LogRecord:
    return logging.LogRecord("app.test", level, __file__, 1, message, None, exc_info)


def test_cloud_format_has_severity_and_message():
    line = CloudLoggingFormatter().format(record(logging.WARNING, "Model failed: čšť"))
    assert json.loads(line) == {"severity": "WARNING", "message": "Model failed: čšť", "logger": "app.test"}


def test_cloud_format_keeps_traceback_in_message():
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys

        line = CloudLoggingFormatter().format(record(logging.ERROR, "Failed", sys.exc_info()))
    entry = json.loads(line)
    assert entry["severity"] == "ERROR"
    assert entry["message"].startswith("Failed\nTraceback") and "RuntimeError: boom" in entry["message"]
