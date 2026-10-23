"""Deliver generated strategy reports to console or Slack."""

import logging
from typing import Protocol

import requests

from models import ChallengeAnalysisResult

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    """Common boundary for report delivery integrations."""

    def send(self, result: ChallengeAnalysisResult, prompt: str) -> None:
        """Deliver a strategy report."""


class ConsoleNotifier:
    """Print strategy reports for local runs and unconfigured delivery."""

    def send(self, result: ChallengeAnalysisResult, prompt: str) -> None:
        """Print the challenge summary and coach prompt."""
        print(
            f"{result.challenge_name}: {result.my_distance_km:.2f}/{result.target_distance_km:.2f} km, "
            f"남은 {result.remaining_distance_km:.2f} km ({result.my_rank}/{result.total_participants}위)"
        )
        print(prompt)


class SlackNotifier:
    """Send a report to a Slack incoming webhook."""

    def __init__(self, webhook_url: str) -> None:
        """Keep the configured webhook URL for delivery."""
        self.webhook_url = webhook_url

    def send(self, result: ChallengeAnalysisResult, prompt: str) -> None:
        """Post a compact metrics summary and the full coach prompt."""
        summary = (
            f"*{result.challenge_name}*\n"
            f"목표: {result.my_distance_km:.2f}/{result.target_distance_km:.2f} km | "
            f"남은 거리: {result.remaining_distance_km:.2f} km | 하루 필요량: {result.daily_req_for_goal:.2f} km/일 | "
            f"순위: {result.my_rank}/{result.total_participants} | 남은 기간: {result.remaining_days}일\n"
            f"1위 격차: {result.gap_to_leader_km:.2f} km (+{result.daily_req_for_leader:.2f} km/일)\n\n{prompt}"
        )
        try:
            response = requests.post(self.webhook_url, json={"text": summary}, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.exception("Slack report delivery failed")
            raise RuntimeError("Could not deliver report to Slack") from exc
