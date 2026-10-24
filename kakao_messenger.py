"""Send each opted-in teammate's running summary to their Kakao My Chatroom."""

import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from models import ChallengeAnalysisResult
from report_page import coach_summary_text, report_page_url

logger = logging.getLogger(__name__)

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


class KakaoMemoSender:
    """Refresh member tokens, send their own-chat messages, and persist rotations."""

    def __init__(self) -> None:
        self.rest_api_key = os.getenv("KAKAO_REST_API_KEY", "")
        self.client_secret = os.getenv("KAKAO_CLIENT_SECRET", "")
        self.sync_url = os.getenv("KAKAO_SYNC_URL", "").rstrip("/")
        self.sync_token = os.getenv("KAKAO_SYNC_TOKEN", "")
        try:
            self.refresh_tokens: dict[str, str] = json.loads(os.getenv("KAKAO_REFRESH_TOKENS_JSON", "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("KAKAO_REFRESH_TOKENS_JSON must contain a JSON object") from exc
        if not isinstance(self.refresh_tokens, dict) or not all(
            isinstance(name, str) and isinstance(token, str) and token
            for name, token in self.refresh_tokens.items()
        ):
            raise ValueError("KAKAO_REFRESH_TOKENS_JSON must map member names to refresh tokens")

    def send(self, result: ChallengeAnalysisResult, report: str) -> None:
        """Send to every configured member; log per-user errors without exposing tokens."""
        self.send_text(coach_summary_text(result, report), report_page_url())

    def send_text(self, text: str, link_url: str | None = None, delivery_date: str | None = None) -> None:
        """Send a prepared summary to every configured member."""
        if not self.refresh_tokens:
            logger.info("Kakao delivery skipped: no member refresh tokens are configured")
            return
        if not self.rest_api_key or not self.client_secret:
            logger.error("Kakao delivery skipped: REST API key or client secret is missing")
            return

        message = {
            "object_type": "text",
            "text": text,
            "link": {"web_url": link_url or "https://jinugkim.github.io/run-teller/",
                     "mobile_web_url": link_url or "https://jinugkim.github.io/run-teller/"},
        }
        delivery_date = delivery_date or datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        sent = 0
        skipped = 0
        failures: list[str] = []
        for member, old_refresh_token in self.refresh_tokens.items():
            try:
                claim = self._claim_delivery(delivery_date, member)
            except (requests.RequestException, ValueError) as exc:
                logger.error("Could not claim Kakao delivery for member %s: %s", member, exc)
                failures.append(member)
                continue
            if not claim["claimed"]:
                skipped += 1
                logger.info("Kakao delivery skipped for member %s: date status is %s", member, claim["status"])
                continue

            try:
                access_token, new_refresh_token = self._refresh(old_refresh_token)
                if new_refresh_token and new_refresh_token != old_refresh_token:
                    self.refresh_tokens[member] = new_refresh_token
                    self._save_rotated_token(member, new_refresh_token)
            except (requests.RequestException, ValueError) as exc:
                if not self._record_delivery(delivery_date, member, "failed", str(exc)):
                    failures.append(f"{member} delivery history")
                logger.error("Kakao token refresh or persistence failed for member %s: %s", member, exc)
                failures.append(member)
                continue

            try:
                self._send_message(access_token, message)
            except requests.RequestException as exc:
                if not self._record_delivery(delivery_date, member, "uncertain", "Kakao request outcome is unknown"):
                    failures.append(f"{member} delivery history")
                logger.error("Kakao delivery outcome is uncertain for member %s: %s", member, exc)
                failures.append(member)
                continue
            except ValueError as exc:
                if not self._record_delivery(delivery_date, member, "failed", str(exc)):
                    failures.append(f"{member} delivery history")
                logger.error("Kakao delivery failed for member %s: %s", member, exc)
                failures.append(member)
                continue

            if self._record_delivery(delivery_date, member, "sent"):
                sent += 1
                logger.info("Kakao summary sent to member %s", member)
            else:
                logger.error("Kakao message sent but delivery history update failed for member %s", member)
                failures.append(member)

        logger.info("Kakao delivery for %s: %d sent, %d already claimed, %d failed", delivery_date, sent, skipped, len(failures))
        if failures:
            raise RuntimeError("Kakao delivery or token sync failed for: " + ", ".join(failures))

    def _claim_delivery(self, delivery_date: str, member: str) -> dict:
        response = requests.post(
            f"{self.sync_url}/internal/deliveries",
            headers={"Authorization": f"Bearer {self.sync_token}"},
            json={"date": delivery_date, "member": member},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "claimed" not in payload:
            raise ValueError("Cloudflare returned an invalid delivery claim")
        return payload

    def _finish_delivery(self, delivery_date: str, member: str, status: str, error: str | None = None) -> None:
        response = requests.put(
            f"{self.sync_url}/internal/deliveries",
            headers={"Authorization": f"Bearer {self.sync_token}"},
            json={"date": delivery_date, "member": member, "status": status, "error": error},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("updated"):
            raise ValueError(f"Cloudflare could not update delivery status for member {member}")

    def _record_delivery(self, delivery_date: str, member: str, status: str, error: str | None = None) -> bool:
        try:
            self._finish_delivery(delivery_date, member, status, error)
            return True
        except (requests.RequestException, ValueError) as exc:
            logger.error("Could not record delivery status %s for member %s: %s", status, member, exc)
            return False

    def _refresh(self, refresh_token: str) -> tuple[str, str | None]:
        response = requests.post(
            KAKAO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self.rest_api_key,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
        if not response.ok:
            try:
                payload = response.json()
                detail = payload.get("error_description") or payload.get("error") or f"HTTP {response.status_code}"
            except ValueError:
                detail = f"HTTP {response.status_code}"
            raise ValueError(f"Kakao token refresh rejected ({detail})")
        payload = response.json()
        return payload["access_token"], payload.get("refresh_token")

    @staticmethod
    def _send_message(access_token: str, message: dict) -> None:
        response = requests.post(
            KAKAO_MEMO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            data={"template_object": json.dumps(message, ensure_ascii=False)},
            timeout=30,
        )
        if not response.ok:
            try:
                payload = response.json()
                detail = payload.get("msg") or payload.get("code") or f"HTTP {response.status_code}"
            except ValueError:
                detail = f"HTTP {response.status_code}"
            raise ValueError(f"Kakao message request rejected ({detail})")

    def _save_rotated_token(self, member: str, refresh_token: str) -> None:
        if not self.sync_url or not self.sync_token:
            raise ValueError("Rotated Kakao tokens cannot be saved: Cloudflare sync URL/token is unavailable")
        response = requests.put(
            f"{self.sync_url}/internal/tokens",
            headers={"Authorization": f"Bearer {self.sync_token}"},
            json={"member": member, "refresh_token": refresh_token},
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"Cloudflare rejected rotated token for member {member}") from exc
        logger.info("Rotated Kakao refresh token saved for member %s", member)
