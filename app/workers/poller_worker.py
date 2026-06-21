import time
from app.gmail.poller import GmailPoller
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def main():
    poller = GmailPoller()
    interval = settings.POLL_INTERVAL_SECONDS
    poll_once = settings.POLL_ONCE

    if poll_once:
        logger.info("Starting Gmail Poller Worker in one-shot mode (CI).")
        poller.poll_once()
        logger.info("Gmail Poller Worker completed one-shot execution and is exiting.")
        return

    logger.info(f"Starting Gmail Poller Worker (interval={interval}s)…")

    while True:
        poller.poll_once()
        time.sleep(interval)


if __name__ == "__main__":
    main()