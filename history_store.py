"""Persist one daily challenge standings snapshot for the Pages report."""

from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from models import ChallengeAnalysisResult

KST = ZoneInfo("Asia/Seoul")
DEFAULT_HISTORY_PATH = Path("data/standings.json")
HISTORY_DAYS = 180


def public_board_enabled() -> bool:
    """Return whether public participant standings should be stored and rendered."""
    return os.getenv("PUBLIC_BOARD_ENABLED", "true").strip().lower() not in {
        "0", "false", "no", "off",
    }


def record_snapshot(
    result: ChallengeAnalysisResult,
    path: Path = DEFAULT_HISTORY_PATH,
    today: datetime | None = None,
) -> dict:
    """Upsert today's standings and return the selected challenge history."""
    if path.exists():
        try:
            history_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read standings history at {path}") from exc
        if history_data.get("schema_version") != 1 or not isinstance(history_data.get("challenges"), dict):
            raise ValueError(f"Unsupported standings history format at {path}")
    else:
        history_data = {"schema_version": 1, "challenges": {}}

    challenge_key = hashlib.sha256(result.challenge_name.casefold().encode("utf-8")).hexdigest()[:16]
    challenge = history_data["challenges"].setdefault(
        challenge_key,
        {
            "challenge_name": result.challenge_name,
            "target_distance_km": result.target_distance_km,
            "snapshots": [],
        },
    )
    now = today or datetime.now(KST)
    snapshot_date = now.astimezone(KST).date() if now.tzinfo else now.date()
    snapshot = {
        "date": snapshot_date.isoformat(),
        "participants": [
            {
                "name": participant.display_name,
                "rank": participant.rank,
                "distance_km": round(participant.distance_km, 2),
                "is_self": participant.is_self,
            }
            for participant in result.participants
        ],
    }
    snapshots = [item for item in challenge["snapshots"] if item.get("date") != snapshot["date"]]
    snapshots.append(snapshot)
    cutoff = snapshot_date - timedelta(days=HISTORY_DAYS - 1)
    challenge["snapshots"] = sorted(
        (item for item in snapshots if item.get("date", "") >= cutoff.isoformat()),
        key=lambda item: item["date"],
    )
    challenge["challenge_name"] = result.challenge_name
    challenge["target_distance_km"] = result.target_distance_km
    for old_key, old_challenge in list(history_data["challenges"].items()):
        old_challenge["snapshots"] = [
            item for item in old_challenge.get("snapshots", [])
            if item.get("date", "") >= cutoff.isoformat()
        ]
        if not old_challenge["snapshots"]:
            del history_data["challenges"][old_key]

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(history_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)
    return challenge
