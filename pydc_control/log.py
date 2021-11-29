"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import logging


# Global vars
_LOGGER: logging.Logger


def init_logger(debug: bool) -> None:
    # pylint: disable=global-statement
    global _LOGGER

    log_level = logging.INFO
    if debug:
        log_level = logging.DEBUG
    log_handler = logging.StreamHandler()
    log_handler.setLevel(log_level)

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.addHandler(log_handler)
    _LOGGER = logger


def get_logger() -> logging.Logger:
    return _LOGGER
