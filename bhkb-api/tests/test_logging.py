import logging

from app.core.logging import setup_logging


def test_setup_logging_sets_level(monkeypatch, caplog):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    caplog.set_level(logging.DEBUG)
    setup_logging()
    logger = logging.getLogger("app.test")
    logger.debug("hello world")
    assert "hello world" in caplog.text
