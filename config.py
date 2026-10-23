"""Load and validate runtime configuration from environment variables."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    garmin_email: str
    garmin_password: str
    garmin_challenge_uuid: str
    token_store_path: Path
    slack_webhook_url: str | None

    @classmethod
    def from_env(cls) -> "Config":
        """Build configuration, reporting missing required environment variables."""
        required = ("GARMIN_EMAIL", "GARMIN_PASSWORD", "GARMIN_CHALLENGE_UUID")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            garmin_email=os.environ["GARMIN_EMAIL"],
            garmin_password=os.environ["GARMIN_PASSWORD"],
            garmin_challenge_uuid=os.environ["GARMIN_CHALLENGE_UUID"],
            token_store_path=Path(os.getenv("TOKEN_STORE_PATH", "~/.garminconnect")).expanduser(),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
        )
