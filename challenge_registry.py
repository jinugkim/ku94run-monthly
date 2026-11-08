"""Load the active monthly challenge and its goals from the annual registry."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

import yaml

KST = ZoneInfo("Asia/Seoul")
DEFAULT_REGISTRY_DIR = Path("data/challenges")
SECRET_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class ChallengeRegistryError(ValueError):
    """Raised when the annual challenge registry is missing valid active data."""


@dataclass(frozen=True)
class ActiveChallenge:
    """The selected challenge and the strictest distance goal across its groups."""

    challenge_id: str
    title: str
    month: int
    garmin_uuid_secret: str
    target_distance_km: float | None
    garmin_uuid: str | None = None


def _date_value(entry: dict[str, Any], key: str) -> date | None:
    value = entry.get(key)
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ChallengeRegistryError(f"Invalid {key} for challenge {entry.get('id', '<unknown>')}") from exc


def _positive_distance(value: Any, challenge_id: str) -> float:
    try:
        distance = float(value)
    except (TypeError, ValueError) as exc:
        raise ChallengeRegistryError(f"Invalid goal distance for challenge {challenge_id}") from exc
    if distance <= 0:
        raise ChallengeRegistryError(f"Goal distance must be positive for challenge {challenge_id}")
    return distance


def _max_goal_distance(entry: dict[str, Any], challenge_id: str) -> float | None:
    group_distances: list[float] = []
    goals = entry.get("goals", [])
    if not isinstance(goals, list):
        raise ChallengeRegistryError(f"Goals must be a list for challenge {challenge_id}")
    for goal in goals:
        if not isinstance(goal, dict):
            raise ChallengeRegistryError(f"Invalid goal entry for challenge {challenge_id}")
        if goal.get("target_distance_km") is not None:
            group_distances.append(_positive_distance(goal["target_distance_km"], challenge_id))

    common_target = entry.get("target_distance_km")
    if common_target is not None:
        common_target = _positive_distance(common_target, challenge_id)
        if group_distances and common_target < max(group_distances):
            raise ChallengeRegistryError(
                f"Common target must be at least the longest tier goal for challenge {challenge_id}"
            )
        return common_target
    return max(group_distances) if group_distances else None


def load_active_challenge(
    today: date | None = None,
    registry_dir: Path = DEFAULT_REGISTRY_DIR,
) -> ActiveChallenge | None:
    """Read the current year's registry and select its one active challenge.

    A missing year file keeps the legacy single-challenge environment path
    available. An existing year file must explicitly name exactly one active
    challenge so a stale UUID cannot silently run for the wrong month.
    """
    today = today or datetime.now(KST).date()
    path = registry_dir / f"{today.year}.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ChallengeRegistryError(f"Could not read challenge registry at {path}") from exc
    if not isinstance(data, dict) or data.get("year") != today.year:
        raise ChallengeRegistryError(f"Challenge registry {path} has an invalid year")
    challenges = data.get("challenges")
    if not isinstance(challenges, list):
        raise ChallengeRegistryError(f"Challenge registry {path} must contain a challenges list")

    active = [entry for entry in challenges if isinstance(entry, dict) and entry.get("status") == "active"]
    if len(active) != 1:
        raise ChallengeRegistryError(
            f"Expected exactly one active challenge in {path}; found {len(active)}"
        )
    entry = active[0]
    challenge_id = str(entry.get("id") or "").strip()
    title = str(entry.get("title") or "").strip()
    garmin_uuid = str(entry.get("garmin_uuid") or entry.get("uuid") or "").strip() or None
    secret_name = str(entry.get("garmin_uuid_secret") or "").strip()
    if not secret_name and garmin_uuid:
        secret_name = f"GARMIN_CHALLENGE_{today.year}_{entry.get('month', today.month):02d}_UUID"
    try:
        month = int(entry.get("month"))
    except (TypeError, ValueError) as exc:
        raise ChallengeRegistryError(f"Invalid month for challenge {challenge_id or '<unknown>'}") from exc
    if not challenge_id or not title:
        raise ChallengeRegistryError(f"Challenge {challenge_id or '<unknown>'} is missing required metadata")
    if not garmin_uuid and (not secret_name or not SECRET_NAME_RE.fullmatch(secret_name)):
        raise ChallengeRegistryError(f"Challenge {challenge_id or '<unknown>'} is missing required metadata")
    if month != today.month:
        raise ChallengeRegistryError(
            f"Active challenge {challenge_id} is for month {month}, but today is in month {today.month}"
        )

    start_date = _date_value(entry, "start_date")
    end_date = _date_value(entry, "end_date")
    if start_date and end_date and start_date > end_date:
        raise ChallengeRegistryError(f"Challenge {challenge_id} has an invalid date range")
    if (start_date and today < start_date) or (end_date and today > end_date):
        raise ChallengeRegistryError(f"Active challenge {challenge_id} is outside its configured date range")

    return ActiveChallenge(
        challenge_id=challenge_id,
        title=title,
        month=month,
        garmin_uuid_secret=secret_name,
        target_distance_km=_max_goal_distance(entry, challenge_id),
        garmin_uuid=garmin_uuid,
    )


def upsert_active_challenge(
    registry_dir: Path,
    year: int,
    month: int,
    title: str,
    uuid: str,
    target_distance_km: float = 200.0,
    goals: list[dict[str, Any]] | None = None,
) -> ActiveChallenge:
    """Upsert the active monthly challenge in the annual registry file."""
    registry_dir.mkdir(parents=True, exist_ok=True)
    path = registry_dir / f"{year}.yaml"

    data: dict[str, Any] = {"year": year, "challenges": []}
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("challenges"), list):
                data = loaded
        except Exception:
            pass

    challenges = data.setdefault("challenges", [])

    # 1. Archive prior active challenges if month doesn't match
    for ch in challenges:
        if isinstance(ch, dict) and ch.get("month") != month and ch.get("status") == "active":
            ch["status"] = "archived"

    # 2. Find or create current month entry
    current_entry = None
    for ch in challenges:
        if isinstance(ch, dict) and ch.get("month") == month:
            current_entry = ch
            break

    challenge_id = f"ku94run-{year}-{month:02d}"
    secret_name = f"GARMIN_CHALLENGE_{year}_{month:02d}_UUID"
    default_goals = goals or [
        {"name": "거북이", "pace_limit_min_per_km": 10, "pace_limit_operator": "<="},
        {"name": "토끼", "pace_limit_min_per_km": 9, "pace_limit_operator": "<="},
    ]

    if current_entry is None:
        current_entry = {
            "id": challenge_id,
            "month": month,
            "title": title,
            "garmin_uuid": uuid,
            "garmin_uuid_secret": secret_name,
            "target_distance_km": target_distance_km,
            "goals": default_goals,
            "status": "active",
        }
        challenges.append(current_entry)
    else:
        current_entry["status"] = "active"
        current_entry["garmin_uuid"] = uuid
        if title:
            current_entry["title"] = title
        if "target_distance_km" not in current_entry:
            current_entry["target_distance_km"] = target_distance_km
        if "goals" not in current_entry:
            current_entry["goals"] = default_goals

    challenges.sort(key=lambda x: x.get("month", 0) if isinstance(x, dict) else 0)

    try:
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    except Exception:
        pass

    return ActiveChallenge(
        challenge_id=challenge_id,
        title=title or current_entry.get("title", ""),
        month=month,
        garmin_uuid_secret=secret_name,
        target_distance_km=_max_goal_distance(current_entry, challenge_id) or target_distance_km,
        garmin_uuid=uuid,
    )
