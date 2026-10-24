"""Run the end-to-end Garmin challenge strategy pipeline."""

import logging
import os

from challenge_analyzer import ChallengeAnalyzer
from config import Config
from courier import ConsoleCourier, Courier, SlackCourier
from garmin_client import GarminSessionManager
from gemini_coach import GeminiCoach
from history_store import record_snapshot
from kakao_messenger import KakaoMemoSender
from prompt_builder import PromptBuilder
from report_page import report_page_url, write_kakao_delivery_payload, write_report_page

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    """Load configuration, analyze a Garmin challenge, and deliver its report."""
    config = Config.from_env()
    client = GarminSessionManager(config.garmin_email, config.garmin_password, str(config.token_store_path))
    raw = client.get_challenge_detail(config.garmin_challenge_uuid)
    result = ChallengeAnalyzer().analyze(raw, target_distance_km=config.challenge_target_distance_km)
    prompt = PromptBuilder().build(result)
    report = GeminiCoach(config.gemini_api_key, config.gemini_model).generate(prompt)
    history = record_snapshot(result)
    write_report_page(result, report, history=history)
    write_kakao_delivery_payload(result, report)
    page_url = report_page_url()
    courier: Courier = SlackCourier(config.slack_webhook_url) if config.slack_webhook_url else ConsoleCourier()
    courier.send(result, report, page_url)
    if os.getenv("KAKAO_SEND_ENABLED", "true").strip().lower() in {"1", "true", "yes"}:
        KakaoMemoSender().send(result, report)


if __name__ == "__main__":
    main()
