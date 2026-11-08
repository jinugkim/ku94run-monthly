"""Run the end-to-end Garmin challenge strategy pipeline."""

from datetime import datetime
import logging
import os
from zoneinfo import ZoneInfo

from archive_pages import archive_completed_snapshots, render_archive_pages
from challenge_analyzer import ChallengeAnalyzer
from challenge_registry import (
    DEFAULT_REGISTRY_DIR,
    load_active_challenge,
    upsert_active_challenge,
)
from config import Config
from courier import ConsoleCourier, Courier, SlackCourier
from garmin_client import GarminSessionManager
from gemini_coach import GeminiCoach
from history_store import public_board_enabled, record_snapshot
from kakao_messenger import KakaoMemoSender
from prompt_builder import PromptBuilder
from report_page import report_page_url, write_kakao_delivery_payload, write_report_page

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
KST = ZoneInfo("Asia/Seoul")


def main() -> None:
    """Load configuration, analyze a Garmin challenge, and deliver its report."""
    config = Config.from_env()
    client = GarminSessionManager(config.garmin_email, config.garmin_password, str(config.token_store_path))
    today = datetime.now(KST).date()

    challenge_uuid: str | None = None
    target_distance_km: float | None = None
    active_challenge = None

    # Step 1: Auto-discover active crew challenge from Garmin Connect
    try:
        discovered = client.discover_crew_challenge(today=today)
        if discovered:
            challenge_uuid, raw_item = discovered
            title = str(
                raw_item.get("challengeName")
                or raw_item.get("adHocChallengeName")
                or raw_item.get("name")
                or f"KU94RUN {today.month}월 챌린지"
            )
            logging.info("Auto-discovered active Garmin challenge: %s (UUID: %s)", title, challenge_uuid)
            active_challenge = upsert_active_challenge(
                registry_dir=DEFAULT_REGISTRY_DIR,
                year=today.year,
                month=today.month,
                title=title,
                uuid=challenge_uuid,
                target_distance_km=config.challenge_target_distance_km or 200.0,
            )
            target_distance_km = active_challenge.target_distance_km
    except Exception as exc:
        logging.warning("Auto-discovery from Garmin Connect encountered an issue: %s", exc)

    # Step 2: Fallback to local registry if auto-discovery did not find a challenge
    if not challenge_uuid:
        try:
            active_challenge = load_active_challenge(today)
            if active_challenge:
                challenge_uuid = active_challenge.garmin_uuid or os.getenv(active_challenge.garmin_uuid_secret)
                target_distance_km = active_challenge.target_distance_km
                if challenge_uuid:
                    logging.info("Selected challenge from registry: %s", active_challenge.challenge_id)
        except Exception as exc:
            logging.info("Registry lookup fallback note: %s", exc)

    # Step 3: Fallback to global environment variable
    if not challenge_uuid:
        challenge_uuid = config.garmin_challenge_uuid

    if target_distance_km is None:
        target_distance_km = (
            active_challenge.target_distance_km
            if active_challenge and active_challenge.target_distance_km is not None
            else config.challenge_target_distance_km
        )

    # If still no challenge found, log a friendly message and return cleanly
    if not challenge_uuid:
        logging.warning(
            "⚠️ 활성 94 러닝 챌린지 UUID를 찾을 수 없습니다. (년-월: %d-%02d)\n"
            "가민 커넥트 앱에서 호스트가 생성한 챌린지에 '참여(Join)'했는지 확인해 주세요.",
            today.year,
            today.month,
        )
        return

    raw = client.get_challenge_detail(challenge_uuid)
    result = ChallengeAnalyzer().analyze(raw, target_distance_km=target_distance_km)
    prompt = PromptBuilder().build(result)
    report = GeminiCoach(config.gemini_api_key, config.gemini_model).generate(prompt)
    board_enabled = public_board_enabled()
    history = record_snapshot(result) if board_enabled else None
    if board_enabled:
        archive_completed_snapshots()
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
