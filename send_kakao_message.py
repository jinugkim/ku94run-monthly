"""Send the summary payload published with the latest GitHub Pages report."""

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kakao_messenger import KakaoMemoSender


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python send_kakao_message.py <payload.json>")
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    text = payload.get("text")
    report_url = payload.get("report_url")
    payload_date = payload.get("date")
    today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    if not isinstance(text, str) or not text or not isinstance(report_url, str) or not report_url:
        raise SystemExit("Kakao payload must contain non-empty text and report_url fields")
    if payload_date != today:
        raise SystemExit("Today's report payload is missing or stale; Kakao message was not sent")
    KakaoMemoSender().send_text(text, report_url, delivery_date=payload_date)


if __name__ == "__main__":
    main()
