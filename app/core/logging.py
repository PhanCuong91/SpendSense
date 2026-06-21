import logging
import sys
from logging.handlers import RotatingFileHandler
from app.core.config import settings

# Defaults — can be adjusted later or moved to config
LOG_FILENAME = "app.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5


def get_logger(name: str):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already initialized

    # Common formatter for both handlers
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stream handler -> stdout (captured by ECS)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Rotating file handler for local file copy
    file_handler = RotatingFileHandler(
        LOG_FILENAME, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.setLevel(settings.LOG_LEVEL.upper())
    logger.propagate = False

    return logger


def save_to_file(content, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(str(content))