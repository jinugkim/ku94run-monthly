"""Render public pages for archived monthly challenge results."""

from html import escape
import json
from pathlib import Path


def render_archive_pages(data_dir: Path = Path("data/archives/2026"), site_dir: Path = Path("site")) -> None:
    archives = []
    if data_dir.exists():
        for path in sorted(data_dir.glob("[0-9][0-9].json")):
            archives.append(json.loads(path.read_text(encoding="utf-8")))
    history_dir = site_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    links = []
    for archive in archives:
        month = int(archive["month"])
        title = escape(str(archive["title"]))
        participants = sorted(archive["participants"], key=lambda p: int(p["rank"]))
        rows = "".join(
            f'<tr><td>{int(p["rank"])}</td><td>{escape(str(p["name"]))}</td>'
            f'<td>{float(p["distance_km"]):.2f} km</td>'
            f'<td>{"달성" if float(p["distance_km"]) >= float(archive["target_distance_km"]) else ""}</td></tr>'
            for p in participants
        )
        page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} 결과</title><style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:30px auto;padding:0 16px;color:#17221e}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}a{{color:#126a4a}}</style>
<p><a href="index.html">← 월별 결과</a></p><h1>{title}</h1><p>최종 기록일: {escape(str(archive["end_date"]))} · 공통 목표: {float(archive["target_distance_km"]):g} km · 참가 {len(participants)}명</p>
<table><thead><tr><th>순위</th><th>러너</th><th>거리</th><th>목표</th></tr></thead><tbody>{rows}</tbody></table></html>'''
        (history_dir / f"2026-{month:02d}.html").write_text(page, encoding="utf-8")
        links.append(f'<li><a href="2026-{month:02d}.html">2026년 {month}월</a> — {title} ({len(participants)}명)</li>')
    body = "".join(links) or "<li>아직 저장된 월별 결과가 없습니다.</li>"
    index = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2026 챌린지 결과</title>
<style>body{{font-family:system-ui,sans-serif;max-width:780px;margin:40px auto;padding:0 18px;color:#17221e}}li{{margin:14px 0}}a{{color:#126a4a}}</style>
<p><a href="../index.html">← 최신 리포트</a></p><h1>2026 월별 챌린지 결과</h1><ul>{body}</ul></html>'''
    (history_dir / "index.html").write_text(index, encoding="utf-8")
