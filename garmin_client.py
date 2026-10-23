"""Small Garmin Connect API wrapper with token reuse."""

import logging
from typing import Any

import requests

try:
    from garminconnect import Garmin
except ImportError:  # Keep importing other modules possible before dependencies are installed.
    Garmin = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class GarminClientError(RuntimeError):
    """Raised when Garmin authentication or challenge retrieval fails."""


class GarminSessionManager:
    """Authenticate to Garmin Connect and retrieve custom challenge details."""

    def __init__(self, email: str, password: str, token_store_path: str) -> None:
        """Store credentials and token location without logging secrets."""
        self.email = email
        self.password = password
        self.token_store_path = token_store_path
        self.client: Any | None = None

    def login(self) -> None:
        """Authenticate using saved tokens first, then fall back to credentials."""
        if Garmin is None:
            raise GarminClientError("garminconnect is not installed; install requirements.txt")
        try:
            client = Garmin(self.email, self.password)
            try:
                client.login(self.token_store_path)
                logger.info("Authenticated with saved Garmin tokens")
            except Exception as token_error:
                logger.info("Saved Garmin tokens unavailable; attempting credential login (%s)", type(token_error).__name__)
                client = Garmin(self.email, self.password)
                client.login()
                client.garth.dump(self.token_store_path)
                logger.info("Garmin tokens saved")
            self.client = client
        except Exception as exc:
            logger.exception("Garmin authentication failed")
            raise GarminClientError("Garmin authentication failed; verify credentials and token configuration") from exc

    def get_challenge_detail(self, challenge_uuid: str) -> dict[str, Any]:
        """Fetch one Garmin ad-hoc challenge through the authenticated API client."""
        if self.client is None:
            self.login()
        assert self.client is not None
        try:
            for method_name in ("get_adhoc_challenge", "get_challenge_detail", "get_challenge"):
                method = getattr(self.client, method_name, None)
                if callable(method):
                    result = method(challenge_uuid)
                    if isinstance(result, dict):
                        profile_id = getattr(self.client, "profile_id", None)
                        if profile_id is not None:
                            result["_currentUserProfileId"] = profile_id
                        return result
            connectapi = getattr(self.client, "connectapi", None)
            if callable(connectapi):
                result = connectapi(f"/adhocchallenge-service/adHocChallenge/{challenge_uuid}")
                if isinstance(result, dict):
                    # Garmin's profile id identifies the signed-in participant in
                    # challenge payloads that do not include an explicit self flag.
                    profile_id = getattr(self.client, "profile_id", None)
                    if profile_id is not None:
                        result["_currentUserProfileId"] = profile_id
                    return result
            raise GarminClientError(
                "Installed garminconnect client does not expose connectapi; upgrade garminconnect"
            )
        except GarminClientError:
            raise
        except requests.exceptions.RequestException as exc:
            logger.exception("Network error fetching Garmin challenge")
            raise GarminClientError("Network error while fetching Garmin challenge") from exc
        except Exception as exc:
            logger.exception("Garmin challenge request failed")
            raise GarminClientError("Garmin challenge request failed; verify the challenge UUID and account access") from exc
