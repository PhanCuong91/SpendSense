import time
from app.correlation.correlator import correlate_once
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def main():
    interval = 60  # run correlation frequently
    logger.info(f"Starting Correlator Worker (interval={interval}s)…")

    while True:
        correlate_once()
        time.sleep(interval)


if __name__ == "__main__":
    main()
