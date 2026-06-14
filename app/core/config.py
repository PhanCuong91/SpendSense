from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    ENV: str = "dev"
    TZ: str = "Asia/Singapore"

    # Database
    DATABASE_URL: str

    # Gmail API
    GMAIL_CREDENTIALS_PATH: str = "credentials.json"
    GMAIL_TOKEN_PATH: str = "token.json"
    GMAIL_CREDENTIALS_JSON: Optional[str] = None
    GMAIL_TOKEN_JSON: Optional[str] = None

    # Pipeline Configuration
    POLL_INTERVAL_SECONDS: int = 300
    CORRELATION_WINDOW_MINUTES: int = 15

    # Logging
    LOG_LEVEL: str = "INFO"

    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
