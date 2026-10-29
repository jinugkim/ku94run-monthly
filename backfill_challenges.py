"""Fetch final Garmin standings for selected archived monthly challenges."""

import json
import os
import sys
from pathlib import Path

import yaml

from challenge_analyzer import ChallengeAnalyzer
from garmin_client import GarminSessionManager


def main() -> None:
    months_arg = os.getenv("BACKFILL_MONTHS", "")
    months = list(range(1, 10)) if months_arg == "all" else [
        int(value) for value in months_arg.split(",") if value
    ]
    if not months or any(month < 1 or month > 9 for month in months):
        raise SystemExit("BACKFILL_MONTHS must be 'all' or a comma-separated list from 1 to 9")

    registry = yaml.safe_load(Path("data/challenges/2026.yaml").read_text(encoding="utf-8"))
    entries = {int(item["month"]): item for item in registry["challenges"]}
    client = GarminSessionManager(
        os.environ["GARMIN_EMAIL"], os.environ["GARMIN_PASSWORD"],
        os.getenv("TOKEN_STORE_PATH", "~/.garminconnect"),
    )
    analyzer = ChallengeAnalyzer()
    for month in months:
        entry = entries[month]
        secret_name = entry["garmin_uuid_secret"]
        challenge_uuid = os.getenv(secret_name)
        if not challenge_uuid:
            raise RuntimeError(f"Missing secret or environment variable: {secret_name}")
        raw = client.get_challenge_detail(challenge_uuid)
        result = analyzer.analyze(raw, target_distance_km=float(entry["target_distance_km"]))
        end_date = entry.get("end_date") or raw.get("endDateLocal") or raw.get("endDate") or "2026"
        participants = [
            {"name": person.display_name, "rank": person.rank,
             "distance_km": round(person.distance_km, 2), "is_self": person.is_self}
            for person in result.participants
        ]
        output = Path(f"data/archives/2026/{month:02d}.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "year": 2026, "month": month, "title": result.challenge_name,
            "end_date": str(end_date), "target_distance_km": result.target_distance_km,
            "achievement_tiers": entry.get("achievement_tiers") or {"rabbit": result.target_distance_km},
            "participants": participants,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {output}: {len(participants)} participants")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Backfill failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
