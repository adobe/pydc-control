
import logging


_LOGGER: logging.Logger = None


def init_logger(debug: bool) -> None:
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
