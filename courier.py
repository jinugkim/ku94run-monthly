"""Deliver challenge summaries and AI coaching reports to output channels."""

import logging
from typing import Protocol

import requests

from models import ChallengeAnalysisResult

logger = logging.getLogger(__name__)


class Courier(Protocol):
    """Interface for console, Slack, KakaoTalk, or future app delivery adapters."""

    def send(self, result: ChallengeAnalysisResult, report: str, report_url: str | None = None) -> None:
        """Deliver one challenge report."""


class ConsoleCourier:
    """Print the challenge summary and AI report to standard output."""

    def send(self, result: ChallengeAnalysisResult, report: str, report_url: str | None = None) -> None:
        """Print a concise progress line followed by the coaching report."""
        print(
            f"{result.challenge_name}: {result.my_distance_km:.2f}/{result.target_distance_km:.2f} km, "
            f"남은 {result.remaining_distance_km:.2f} km ({result.my_rank}/{result.total_participants}위)"
        )
        print(report)
        if report_url:
            print(f"상세 리포트: {report_url}")


class SlackCourier:
    """Send the challenge summary and AI report to a Slack webhook."""

    def __init__(self, webhook_url: str) -> None:
        """Store a Slack incoming webhook URL."""
        self.webhook_url = webhook_url

    def send(self, result: ChallengeAnalysisResult, report: str, report_url: str | None = None) -> None:
        """Post goal progress, standings, and the generated coaching report."""
        text = (
            f"*{result.challenge_name}*\n"
            f"목표: {result.my_distance_km:.2f}/{result.target_distance_km:.2f} km | "
            f"남은 거리: {result.remaining_distance_km:.2f} km | "
            f"하루 필요량: {result.daily_req_for_goal:.2f} km/일 | "
            f"순위: {result.my_rank}/{result.total_participants} | 남은 기간: {result.remaining_days}일\n\n"
            f"{report}\n\n"
            + (f"<상세 리포트|{report_url}>" if report_url else "")
        )
        try:
            response = requests.post(self.webhook_url, json={"text": text}, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.exception("Slack report delivery failed")
            raise RuntimeError("Could not deliver report to Slack") from exc
