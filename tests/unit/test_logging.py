import json
import logging

import structlog

from app.logging import configure_logging


def test_configure_logging_emits_json(capsys):
    configure_logging(level="INFO")
    log = structlog.get_logger("test")
    log.info("hello", foo="bar")
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"] == "hello"
    assert payload["foo"] == "bar"
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_stdlib_logging_routed_through_structlog(capsys):
    configure_logging(level="INFO")
    logging.getLogger("xyz").warning("legacy %s", "msg")
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"].startswith("legacy")
    assert payload["level"] == "warning"
