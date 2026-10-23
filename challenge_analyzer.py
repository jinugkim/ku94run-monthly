"""Parse Garmin challenge payloads and calculate distance strategy metrics."""

from datetime import date, datetime
import re
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

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


def _is_uuid(value: Any) -> bool:
    """Return whether a candidate display name is actually a UUID identifier."""
    try:
        UUID(str(value).strip())
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _display_name(entry: dict[str, Any], rank: int) -> str:
    """Prefer a human-readable profile name over Garmin's UUID-like displayName."""
    profiles = [
        entry.get("userProfile"),
        entry.get("participant"),
        entry.get("userInfo"),
    ]
    candidates: list[Any] = []
    for profile in profiles:
        if isinstance(profile, dict):
            candidates.extend(profile.get(field) for field in ("displayName", "userName", "fullName", "name"))
    candidates.extend(entry.get(field) for field in ("displayName", "userName", "fullName", "name"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip() and not _is_uuid(candidate):
            return candidate.strip()
    return f"참가자 {rank}"


class ChallengeAnalyzer:
    """Extract participant standings and compute rank gap targets."""

    def analyze(
        self,
        raw: dict[str, Any],
        today: date | None = None,
        target_distance_km: float | None = None,
    ) -> ChallengeAnalysisResult:
        """Analyze challenge standings and the distance goal using configured or titled target."""
        today = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
        name = str(raw.get("challengeName") or raw.get("adHocChallengeName") or raw.get("name") or "Garmin Challenge")
        goal_match = re.search(r"(\d+(?:[.,]\d+)?)\s*km\b", name, re.IGNORECASE)
        if target_distance_km is None and goal_match:
            target_distance_km = float(goal_match.group(1).replace(",", "."))
        if target_distance_km is None or target_distance_km <= 0:
            raise ChallengeDataError(
                "Challenge target distance is unknown; set GARMIN_CHALLENGE_TARGET_KM (for example, 200)"
            )
        end_date_value = raw.get("endDate") or raw.get("endDateLocal")
        remaining_days = max(1, (_parse_date(end_date_value) - today).days)
        people = raw.get("participants") or raw.get("participantProgress") or raw.get("leaderboard") or raw.get("players")
        if not isinstance(people, list) or not people:
            raise ChallengeDataError("Challenge payload contains no participant standings")

        parsed: list[ParticipantProgress] = []
        for entry in people:
            if not isinstance(entry, dict):
                continue
            rank_value = (
                entry.get("rank") or entry.get("rankNumber") or entry.get("ranking")
                or entry.get("userRanking") or len(parsed) + 1
            )
            name_value = _display_name(entry, int(rank_value))
            distance = entry.get(
                "value",
                entry.get("distance", entry.get("totalDistance", entry.get("totalNumber", entry.get("progress", 0)))),
            )
            current_user_id = raw.get(
                "_currentUserProfileId", raw.get("currentUserId", raw.get("userProfileId", raw.get("userId")))
            )
            participant_id = entry.get("userProfileId", entry.get("userProfilePk", entry.get("userId")))
            own_rank = raw.get("userRanking")
            is_self = bool(
                entry.get("isSelf")
                or entry.get("isCurrentUser")
                or (current_user_id is not None and participant_id is not None and str(participant_id) == str(current_user_id))
                or (own_rank is not None and int(rank_value) == int(own_rank))
            )
            parsed.append(
                ParticipantProgress(
                    display_name=str(name_value),
                    rank=int(rank_value),
                    distance_km=_number(distance) / 1000,
                    is_self=is_self,
                )
            )
        if not parsed:
            raise ChallengeDataError("Challenge standings could not be parsed")
        parsed.sort(key=lambda participant: (participant.rank, -participant.distance_km))
        self_rows = [p for p in parsed if p.is_self]
        if len(self_rows) != 1:
            raise ChallengeDataError("Could not uniquely identify the current user in challenge standings")
        me = self_rows[0]
        remaining_distance = max(0.0, target_distance_km - me.distance_km)
        daily_req_for_goal = remaining_distance / remaining_days
        above = [participant for participant in parsed if participant.rank < me.rank]
        leader = parsed[0]
        target = max(above, key=lambda p: p.rank) if above else me
        gap_leader = max(0.0, leader.distance_km - me.distance_km)
        gap_target = max(0.0, target.distance_km - me.distance_km)
        return ChallengeAnalysisResult(
            challenge_name=name, remaining_days=remaining_days, target_distance_km=target_distance_km,
            remaining_distance_km=remaining_distance, daily_req_for_goal=daily_req_for_goal,
            total_participants=len(parsed), my_rank=me.rank,
            my_distance_km=me.distance_km, leader_distance_km=leader.distance_km,
            target_rank_distance_km=target.distance_km, gap_to_leader_km=gap_leader,
            gap_to_target_km=gap_target, daily_req_for_leader=gap_leader / remaining_days,
            daily_req_for_target=gap_target / remaining_days,
            participants=parsed,
        )
