"""Parse Garmin challenge payloads and calculate distance strategy metrics."""

from datetime import date, datetime
from typing import Any

from models import ChallengeAnalysisResult, ParticipantProgress


class ChallengeDataError(ValueError):
    """Raised when a Garmin challenge payload lacks usable standings."""


def _number(value: Any) -> float:
    """Convert a Garmin numeric value to a float, treating missing values as zero."""
    if isinstance(value, dict):
        value = value.get("value", value.get("sum", 0))
    try:
        return float(value or 0)
    except (TypeError, ValueError) as exc:
        raise ChallengeDataError(f"Invalid distance value: {value!r}") from exc


def _parse_date(value: Any) -> date:
    """Parse Garmin date strings or timestamps into a date."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value).date()
    if not isinstance(value, str):
        raise ChallengeDataError("Challenge end date is missing")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ChallengeDataError(f"Unrecognized challenge end date: {value!r}") from exc


class ChallengeAnalyzer:
    """Extract participant standings and compute rank gap targets."""

    def analyze(self, raw: dict[str, Any], today: date | None = None) -> ChallengeAnalysisResult:
        """Analyze Garmin challenge JSON using the current date unless supplied."""
        today = today or date.today()
        name = str(raw.get("challengeName") or raw.get("name") or "Garmin Challenge")
        end_date_value = raw.get("endDate") or raw.get("endDateLocal")
        remaining_days = max(1, (_parse_date(end_date_value) - today).days)
        people = raw.get("participants") or raw.get("participantProgress") or raw.get("leaderboard")
        if not isinstance(people, list) or not people:
            raise ChallengeDataError("Challenge payload contains no participant standings")

        parsed: list[ParticipantProgress] = []
        for entry in people:
            if not isinstance(entry, dict):
                continue
            profile = entry.get("userProfile") or entry.get("participant") or {}
            if not isinstance(profile, dict):
                profile = {}
            name_value = entry.get("displayName") or profile.get("displayName") or profile.get("userName") or "Participant"
            rank_value = entry.get("rank") or entry.get("rankNumber") or len(parsed) + 1
            distance = entry.get("value", entry.get("distance", entry.get("totalDistance", 0)))
            current_user_id = raw.get("currentUserId", raw.get("userId"))
            is_self = bool(
                entry.get("isSelf")
                or entry.get("isCurrentUser")
                or (current_user_id is not None and entry.get("userId") == current_user_id)
            )
            parsed.append(ParticipantProgress(str(name_value), int(rank_value), _number(distance) / 1000, is_self))
        if not parsed:
            raise ChallengeDataError("Challenge standings could not be parsed")
        parsed.sort(key=lambda participant: (participant.rank, -participant.distance_km))
        self_rows = [p for p in parsed if p.is_self]
        if len(self_rows) != 1:
            raise ChallengeDataError("Could not uniquely identify the current user in challenge standings")
        me = self_rows[0]
        above = [participant for participant in parsed if participant.rank < me.rank]
        leader = parsed[0]
        target = max(above, key=lambda p: p.rank) if above else me
        gap_leader = max(0.0, leader.distance_km - me.distance_km)
        gap_target = max(0.0, target.distance_km - me.distance_km)
        return ChallengeAnalysisResult(
            challenge_name=name, remaining_days=remaining_days, total_participants=len(parsed), my_rank=me.rank,
            my_distance_km=me.distance_km, leader_distance_km=leader.distance_km,
            target_rank_distance_km=target.distance_km, gap_to_leader_km=gap_leader,
            gap_to_target_km=gap_target, daily_req_for_leader=gap_leader / remaining_days,
            daily_req_for_target=gap_target / remaining_days,
        )
