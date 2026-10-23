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
    challenge_target_distance_km: float | None
    gemini_api_key: str
    gemini_model: str

    @classmethod
    def from_env(cls) -> "Config":
        """Build configuration, reporting missing required environment variables."""
        required = ("GARMIN_EMAIL", "GARMIN_PASSWORD", "GARMIN_CHALLENGE_UUID")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        target_value = os.getenv("GARMIN_CHALLENGE_TARGET_KM")
        try:
            target_distance = float(target_value) if target_value else None
        except ValueError as exc:
            raise ValueError("GARMIN_CHALLENGE_TARGET_KM must be a positive number") from exc
        if target_distance is not None and target_distance <= 0:
            raise ValueError("GARMIN_CHALLENGE_TARGET_KM must be a positive number")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("Missing required environment variable: GEMINI_API_KEY")
        return cls(
            garmin_email=os.environ["GARMIN_EMAIL"],
            garmin_password=os.environ["GARMIN_PASSWORD"],
            garmin_challenge_uuid=os.environ["GARMIN_CHALLENGE_UUID"],
            token_store_path=Path(os.getenv("TOKEN_STORE_PATH", "~/.garminconnect")).expanduser(),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
            challenge_target_distance_km=target_distance,
            gemini_api_key=gemini_api_key,
            gemini_model=os.getenv("GEMINI_MODEL") or "gemini-3.8-flash",
        )
