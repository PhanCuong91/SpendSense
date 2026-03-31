import logging
import sys
from app.core.config import settings
import time
log_name = f'app_1.log'

def get_logger(name: str):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already initialized

    file_handler = logging.FileHandler(log_name, encoding='utf-8')
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.setLevel(settings.LOG_LEVEL.upper())
    logger.propagate = False

    return logger

def save_to_file(content, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(str(content))