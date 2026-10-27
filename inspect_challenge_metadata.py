"""Inspect Garmin challenge goal metadata without printing participant data."""

import json
import os
import re
import sys
from typing import Any

from garmin_client import GarminSessionManager

GOAL_KEY = re.compile(r"goal|target|distance|metric|threshold|unit|rule", re.IGNORECASE)
PRIVATE_LIST_KEYS = {"participants", "participantprogress", "leaderboard", "players"}


def find_goal_fields(value: Any, path: str = "") -> list[dict[str, Any]]:
    """Return only goal-related scalar fields, skipping participant collections."""
    matches: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if key.casefold() in PRIVATE_LIST_KEYS:
                continue
            if GOAL_KEY.search(key) and not isinstance(child, (dict, list)):
                matches.append({"path": child_path, "value": child})
            matches.extend(find_goal_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(find_goal_fields(child, f"{path}[{index}]"))
    return matches


def main() -> None:
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    challenge_uuid = os.getenv("GARMIN_CHALLENGE_INSPECT_UUID")
    if not email or not password or not challenge_uuid:
        raise SystemExit("Missing Garmin credentials or inspection challenge UUID")

    client = GarminSessionManager(
        email,
        password,
        os.getenv("TOKEN_STORE_PATH", "~/.garminconnect"),
    )
    raw = client.get_challenge_detail(challenge_uuid)
    name = raw.get("challengeName") or raw.get("adHocChallengeName") or raw.get("name")
    fields = find_goal_fields(raw)
    print(json.dumps({"challenge_name": name, "goal_related_fields": fields}, ensure_ascii=False, indent=2))
    if not fields:
        print("No obvious goal-related fields found; inspect the challenge title/rules manually.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Inspection failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from exc
