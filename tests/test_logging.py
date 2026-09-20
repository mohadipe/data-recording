import logging

from data_recorder.core.logging import setup_logging


def test_setup_logging():
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG

    setup_logging("INFO")
    assert logging.getLogger().level == logging.INFO
