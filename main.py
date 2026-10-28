"""Run the end-to-end Garmin challenge strategy pipeline."""

import logging
import os

from archive_pages import render_archive_pages
from challenge_analyzer import ChallengeAnalyzer
from challenge_registry import load_active_challenge
from config import Config
from courier import ConsoleCourier, Courier, SlackCourier
from garmin_client import GarminSessionManager
from gemini_coach import GeminiCoach
from history_store import public_board_enabled, record_snapshot
from kakao_messenger import KakaoMemoSender
from prompt_builder import PromptBuilder
from report_page import report_page_url, write_kakao_delivery_payload, write_report_page

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    """Load configuration, analyze a Garmin challenge, and deliver its report."""
    config = Config.from_env()
    active_challenge = load_active_challenge()
    if active_challenge:
        challenge_uuid = os.getenv(active_challenge.garmin_uuid_secret)
        if not challenge_uuid:
            raise ValueError(
                f"Missing GitHub Actions Secret or environment variable: {active_challenge.garmin_uuid_secret}"
            )
        logging.info("Selected registered challenge %s", active_challenge.challenge_id)
    else:
        challenge_uuid = config.garmin_challenge_uuid
        if not challenge_uuid:
            raise ValueError("Missing GARMIN_CHALLENGE_UUID and no active annual challenge is configured")

    target_distance_km = (
        active_challenge.target_distance_km
        if active_challenge and active_challenge.target_distance_km is not None
        else config.challenge_target_distance_km
    )
    client = GarminSessionManager(config.garmin_email, config.garmin_password, str(config.token_store_path))
    raw = client.get_challenge_detail(challenge_uuid)
    result = ChallengeAnalyzer().analyze(raw, target_distance_km=target_distance_km)
    prompt = PromptBuilder().build(result)
    report = GeminiCoach(config.gemini_api_key, config.gemini_model).generate(prompt)
    board_enabled = public_board_enabled()
    history = record_snapshot(result) if board_enabled else None
    render_archive_pages()
    write_report_page(result, report, history=history, public_board_enabled=board_enabled)
    write_kakao_delivery_payload(result, report)
    page_url = report_page_url()
    courier: Courier = SlackCourier(config.slack_webhook_url) if config.slack_webhook_url else ConsoleCourier()
    courier.send(result, report, page_url)
    if os.getenv("KAKAO_SEND_ENABLED", "true").strip().lower() in {"1", "true", "yes"}:
        KakaoMemoSender().send(result, report)


if __name__ == "__main__":
    main()
