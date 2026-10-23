"""Run the end-to-end Garmin challenge strategy pipeline."""

import logging

from challenge_analyzer import ChallengeAnalyzer
from config import Config
from garmin_client import GarminSessionManager
from notifier import ConsoleNotifier, Notifier, SlackNotifier
from prompt_builder import PromptBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    """Load configuration, analyze a Garmin challenge, and deliver its report."""
    config = Config.from_env()
    client = GarminSessionManager(config.garmin_email, config.garmin_password, str(config.token_store_path))
    raw = client.get_challenge_detail(config.garmin_challenge_uuid)
    result = ChallengeAnalyzer().analyze(raw, target_distance_km=config.challenge_target_distance_km)
    prompt = PromptBuilder().build(result)
    notifier: Notifier = SlackNotifier(config.slack_webhook_url) if config.slack_webhook_url else ConsoleNotifier()
    notifier.send(result, prompt)


if __name__ == "__main__":
    main()
