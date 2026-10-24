"""Locally authorize one teammate and add their Kakao refresh token to a JSON file."""

import json
import os
import secrets
import threading
import time
import webbrowser
from getpass import getpass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests

REDIRECT_URI = "http://localhost:8765/oauth/callback"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_FILE = Path("kakao_refresh_tokens.json")


class CallbackHandler(BaseHTTPRequestHandler):
    state: str
    result: Optional[Dict[str, str]] = None
    received = threading.Event()

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        if urlparse(self.path).path != "/oauth/callback" or query.get("state", [""])[0] != self.state:
            self.send_error(400, "Invalid OAuth callback")
            return
        if "error" in query:
            type(self).result = {"error": query["error"][0]}
        else:
            type(self).result = {"code": query.get("code", [""])[0]}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h1>카카오 인증 응답을 받았습니다. 이 창을 닫으세요.</h1>".encode())
        type(self).received.set()

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    member = input("저장할 팀원 식별자(예: jinugkim): ").strip()
    rest_api_key = os.getenv("KAKAO_REST_API_KEY", "").strip() or getpass("Kakao REST API key: ").strip()
    client_secret = os.getenv("KAKAO_CLIENT_SECRET", "").strip() or getpass("Kakao login client secret: ").strip()
    if not member or not rest_api_key or not client_secret:
        raise SystemExit("팀원 식별자와 KAKAO_REST_API_KEY, KAKAO_CLIENT_SECRET 환경 변수가 필요합니다.")

    CallbackHandler.state = secrets.token_urlsafe(32)
    CallbackHandler.result = None
    CallbackHandler.received.clear()
    server = HTTPServer(("127.0.0.1", 8765), CallbackHandler)
    server.timeout = 1
    try:
        login_url = AUTH_URL + "?" + urlencode({
            "client_id": rest_api_key,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "talk_message",
            "state": CallbackHandler.state,
        })
        print("브라우저에서 카카오 로그인 및 메시지 권한 동의를 진행합니다.")
        webbrowser.open(login_url)
        deadline = time.monotonic() + 300
        while not CallbackHandler.received.is_set() and time.monotonic() < deadline:
            server.handle_request()
        if not CallbackHandler.received.is_set() or not CallbackHandler.result:
            raise SystemExit("인증 응답을 받지 못했습니다. 다시 실행해 주세요.")
        if "error" in CallbackHandler.result:
            raise SystemExit(f"카카오 인증이 취소되거나 실패했습니다: {CallbackHandler.result['error']}")

        response = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": rest_api_key,
            "redirect_uri": REDIRECT_URI,
            "code": CallbackHandler.result["code"],
            "client_secret": client_secret,
        }, timeout=30)
        if not response.ok:
            raise SystemExit(f"토큰 교환 실패(HTTP {response.status_code}). Kakao 설정과 리다이렉트 URI를 확인해 주세요.")
        refresh_token = response.json().get("refresh_token")
        if not refresh_token:
            raise SystemExit("카카오 응답에 refresh_token이 없습니다. talk_message 동의 설정을 확인해 주세요.")

        token_map: Dict[str, str] = {}
        if TOKEN_FILE.exists():
            token_map = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        token_map[member] = refresh_token
        TOKEN_FILE.write_text(json.dumps(token_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            TOKEN_FILE.chmod(0o600)
        except OSError:
            pass
        print(f"{member}의 토큰을 {TOKEN_FILE}에 저장했습니다. 이 파일을 저장소에 커밋하지 마세요.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
