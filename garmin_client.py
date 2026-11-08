"""Small Garmin Connect API wrapper with token reuse."""

from datetime import date, datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

import requests

try:
    from garminconnect import Garmin
except ImportError:  # Keep importing other modules possible before dependencies are installed.
    Garmin = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


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

    def get_active_adhoc_challenges(self) -> list[dict[str, Any]]:
        """Fetch active ad-hoc challenges the user is currently participating in."""
        if self.client is None:
            self.login()
        assert self.client is not None

        # Try library helper methods first
        for method_name in ("get_active_adhoc_challenges", "get_adhoc_challenges"):
            method = getattr(self.client, method_name, None)
            if callable(method):
                try:
                    res = method(1, 100) if method_name == "get_adhoc_challenges" else method()
                    items = self._normalize_challenge_list(res)
                    if items:
                        logger.info("Retrieved %d challenges using %s", len(items), method_name)
                        return items
                except Exception as exc:
                    logger.debug("Method %s failed: %s", method_name, exc)

        # Fallback to direct Garmin connectapi endpoints
        connectapi = getattr(self.client, "connectapi", None)
        if callable(connectapi):
            for endpoint in (
                "/adhocchallenge-service/adHocChallenge/inProgress",
                "/adhocchallenge-service/adHocChallenge/historical?start=1&limit=30",
            ):
                try:
                    res = connectapi(endpoint)
                    items = self._normalize_challenge_list(res)
                    if items:
                        logger.info("Retrieved %d challenges using %s", len(items), endpoint)
                        return items
                except Exception as exc:
                    logger.debug("connectapi %s failed: %s", endpoint, exc)

        logger.warning("Could not retrieve active ad-hoc challenges list from Garmin Connect")
        return []

    @staticmethod
    def _normalize_challenge_list(raw: Any) -> list[dict[str, Any]]:
        """Extract a list of challenge dictionaries from varied API response shapes."""
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        if isinstance(raw, dict):
            for key in ("adHocChallenges", "challenges", "entries", "content"):
                if isinstance(raw.get(key), list):
                    return [x for x in raw[key] if isinstance(x, dict)]
        return []

    def discover_crew_challenge(
        self,
        keywords: tuple[str, ...] = ("ku94", "94", "고려"),
        today: date | None = None,
    ) -> tuple[str, dict[str, Any]] | None:
        """Find an active running challenge matching crew keywords and current date range."""
        today = today or datetime.now(KST).date()
        challenges = self.get_active_adhoc_challenges()
        if not challenges:
            return None

        candidates = []
        for item in challenges:
            name = str(
                item.get("challengeName")
                or item.get("adHocChallengeName")
                or item.get("name")
                or item.get("title")
                or ""
            )
            name_lower = name.lower()
            if not any(kw.lower() in name_lower for kw in keywords):
                continue

            uuid = (
                item.get("adHocChallengeUuid")
                or item.get("challengeUuid")
                or item.get("challengeId")
                or item.get("uuid")
            )
            if not uuid:
                continue

            # Check date range
            start_val = item.get("startDate") or item.get("startDateLocal")
            end_val = item.get("endDate") or item.get("endDateLocal")
            in_range = False
            month_matches = False

            if start_val and end_val:
                try:
                    s_str = str(start_val)[:10]
                    e_str = str(end_val)[:10]
                    s_date = date.fromisoformat(s_str)
                    e_date = date.fromisoformat(e_str)
                    in_range = (s_date <= today <= e_date)
                    month_matches = (s_date.year == today.year and s_date.month == today.month)
                except Exception:
                    in_range = True

            candidates.append((in_range, month_matches, str(uuid), item))

        if not candidates:
            return None

        # Prioritize (in_range, month_matches)
        candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
        _, _, best_uuid, best_item = candidates[0]
        return best_uuid, best_item
