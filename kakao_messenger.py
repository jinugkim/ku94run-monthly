"""Send each opted-in teammate's running summary to their Kakao My Chatroom."""

import base64
import json
import logging
import os

import requests
from nacl.public import PublicKey, SealedBox

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
        self.tokens_secret_name = os.getenv("KAKAO_REFRESH_TOKENS_SECRET_NAME", "KAKAO_REFRESH_TOKENS_JSON")
        self.github_token = os.getenv("GH_APP_TOKEN", "")
        self.repository = os.getenv("GITHUB_REPOSITORY", "")
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
        if not self.refresh_tokens:
            logger.info("Kakao delivery skipped: no member refresh tokens are configured")
            return
        if not self.rest_api_key or not self.client_secret:
            logger.error("Kakao delivery skipped: REST API key or client secret is missing")
            return

        message = {
            "object_type": "text",
            "text": coach_summary_text(result, report),
            "link": {"web_url": report_page_url() or "https://jinugkim.github.io/run-teller/",
                     "mobile_web_url": report_page_url() or "https://jinugkim.github.io/run-teller/"},
        }
        rotated = False
        sent = 0
        for member, old_refresh_token in self.refresh_tokens.items():
            try:
                access_token, new_refresh_token = self._refresh(old_refresh_token)
                if new_refresh_token and new_refresh_token != old_refresh_token:
                    self.refresh_tokens[member] = new_refresh_token
                    rotated = True
                self._send_message(access_token, message)
                sent += 1
                logger.info("Kakao summary sent to member %s", member)
            except (requests.RequestException, ValueError) as exc:
                logger.error("Kakao delivery failed for member %s: %s", member, exc)

        if rotated:
            self._save_rotated_tokens()
        logger.info("Kakao summary delivery complete: %d/%d sent", sent, len(self.refresh_tokens))

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

    def _save_rotated_tokens(self) -> None:
        if not self.github_token or "/" not in self.repository:
            raise ValueError("Rotated Kakao tokens cannot be saved: GitHub App token/repository is unavailable")
        public_key_response = requests.get(
            f"https://api.github.com/repos/{self.repository}/actions/secrets/public-key",
            headers=self._github_headers(),
            timeout=30,
        )
        public_key_response.raise_for_status()
        public_key = public_key_response.json()
        box = SealedBox(PublicKey(base64.b64decode(public_key["key"])))
        encrypted_value = base64.b64encode(
            box.encrypt(json.dumps(self.refresh_tokens, separators=(",", ":")).encode("utf-8"))
        ).decode("ascii")
        response = requests.put(
            f"https://api.github.com/repos/{self.repository}/actions/secrets/{self.tokens_secret_name}",
            headers=self._github_headers(),
            json={"encrypted_value": encrypted_value, "key_id": public_key["key_id"]},
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Rotated Kakao refresh tokens saved to GitHub Actions secret %s", self.tokens_secret_name)

    def _github_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
