import logging
import sys
from app.core.config import settings


def get_logger(name: str):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already initialized

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(settings.LOG_LEVEL.upper())
    logger.propagate = False

    return logger