"""Render public pages for archived monthly challenge results."""

from html import escape
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


def load_archives(data_root: Path = Path("data/archives")) -> list[dict]:
    archives = []
    if data_root.exists():
        for path in sorted(data_root.glob("*/[0-9][0-9].json")):
            archives.append(json.loads(path.read_text(encoding="utf-8")))
    return sorted(archives, key=lambda item: (int(item["year"]), int(item["month"])))


def _rabbit_icon(super_rabbit: bool = False) -> str:
    """Return a small accessible inline SVG badge for rabbit finishers."""
    if super_rabbit:
        drawing = (
            '<path d="M5 15c0-4 3-7 7-7 1 0 2 .2 3 .7L17 5l1 6c2 1 3 3 3 5v2H7a2 2 0 0 1-2-2z"/>'
            '<path d="M9 9 7 2c-.3-1.3 1.5-1.8 2.1-.6L12 7M14 8l1-7c.2-1.3 2-.9 2 .4L17 11"/>'
            '<path d="m19 2 .8 1.8L22 4l-1.6 1.2.5 2-1.9-1.1-1.8 1.1.4-2L16 4l2-.2z" fill="#b08a42" stroke="none"/>'
            '<path d="M5 16 1 20l6-1" fill="#7a1735" stroke="#7a1735"/>'
        )
        aria_label = "슈퍼토끼 목표 달성"
        color = "#5d1028"
    else:
        drawing = (
            '<path d="M5 16c0-4 3-7 7-7s7 3 7 7v2H5z"/>'
            '<path d="M9 10 7.5 3c-.3-1.3 1.5-1.8 2-.5L12 9M14 9l1-6.5c.2-1.3 2-.9 2 .4L17 11"/>'
            '<circle cx="10" cy="14" r=".7" fill="#fffdfb" stroke="none"/><circle cx="15" cy="14" r=".7" fill="#fffdfb" stroke="none"/>'
            '<path d="M11 16q1.5 1.5 3 0" fill="none" stroke="#fffdfb" stroke-width=".8"/>'
        )
        aria_label = "토끼 목표 달성"
        color = "#7a1735"
    return (
        f'<svg class="achievement-icon" viewBox="0 0 24 24" role="img" aria-label="{aria_label}" '
        f'xmlns="http://www.w3.org/2000/svg"><g fill="{color}" stroke="{color}" stroke-width="1.2" '
        f'stroke-linecap="round" stroke-linejoin="round">{drawing}</g></svg>'
    )


def _visible_participants(participants: list[dict]) -> list[dict]:
    """Omit participants who have not recorded any distance in the challenge."""
    return [person for person in participants if float(person.get("distance_km", 0)) > 0]


def _participants_table_with_tiers(participants: list[dict], achievement_tiers: dict) -> str:
    participants = _visible_participants(participants)
    rabbit_goal = float(achievement_tiers.get("rabbit", achievement_tiers.get("target_distance_km", 0)))
    super_goal = achievement_tiers.get("superrabbit")
    super_goal = float(super_goal) if super_goal is not None else None
    rows = "".join(
        f'<tr><td>{int(p["rank"])}</td><td>{escape(str(p["name"]))}</td>'
        f'<td>{float(p["distance_km"]):.2f} km</td>'
        f'<td>{_rabbit_icon(True) + " 슈퍼토끼" if super_goal is not None and float(p["distance_km"]) >= super_goal else _rabbit_icon() + " 토끼" if rabbit_goal and float(p["distance_km"]) >= rabbit_goal else "—"}</td></tr>'
        for p in sorted(participants, key=lambda person: int(person["rank"]))
    )
    return (
        '<div class="archive-table-wrap"><table><thead><tr><th>순위</th><th>러너</th>'
        f'<th>거리</th><th>달성</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


def archive_section_html(data_root: Path = Path("data/archives"), current_result=None) -> str:
    """Return an accessible year selector and monthly result tabs for the home page."""
    archives = load_archives(data_root)
    current_month_key = None
    if current_result is not None:
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        current_month_key = (now.year, now.month)
        archives = [
            archive for archive in archives
            if (int(archive["year"]), int(archive["month"])) != current_month_key
        ]
        archives.append({
            "year": now.year,
            "month": now.month,
            "title": current_result.challenge_name,
            "end_date": f"진행 중 · {now:%Y-%m-%d} 기준",
            "target_distance_km": current_result.target_distance_km,
            "achievement_tiers": {"rabbit": current_result.target_distance_km},
            "participants": [
                {"name": participant.display_name, "rank": participant.rank,
                 "distance_km": round(participant.distance_km, 2)}
                for participant in current_result.participants
            ],
            "is_current": True,
        })
    archives = sorted(archives, key=lambda item: (int(item["year"]), int(item["month"])), reverse=True)
    if not archives:
        return '<section class="archive-section"><h2>지난 챌린지</h2><p>지난달 결과가 아직 없습니다.</p></section>'
    years = sorted({int(item["year"]) for item in archives}, reverse=True)
    selected_year = current_month_key[0] if current_month_key else years[0]
    latest = current_month_key or max(
        (int(item["year"]), int(item["month"])) for item in archives
    )
    year_tabs = "".join(
        f'<button class="archive-year-tab" type="button" role="tab" data-year="{year}" '
        f'aria-selected="{str(year == selected_year).lower()}">{year}</button>'
        for year in years
    )
    tabs = []
    panels = []
    for archive in archives:
        year = int(archive["year"])
        month = int(archive["month"])
        selected = (year, month) == latest
        tab_id = f"archive-tab-{year}-{month:02d}"
        panel_id = f"archive-panel-{year}-{month:02d}"
        current = bool(archive.get("is_current"))
        current_badge = '<small class="archive-current-badge">진행 중</small>' if current else ""
        tabs.append(
            f'<button class="archive-tab" id="{tab_id}" type="button" role="tab" '
            f'aria-controls="{panel_id}" aria-selected="{str(selected).lower()}" '
            f'data-year="{year}" data-month="{month:02d}">{month}월{current_badge}</button>'
        )
        title = escape(str(archive["title"]))
        participants = _visible_participants(archive["participants"])
        tiers = archive.get("achievement_tiers") or {"rabbit": archive["target_distance_km"]}
        panels.append(
            f'<section class="archive-panel" id="{panel_id}" role="tabpanel" aria-labelledby="{tab_id}" '
            f'data-year="{year}"{"" if selected else " hidden"}>'
            f'<h3>{year}년 {month}월 · {title}</h3>'
            f'<p class="muted">{escape(str(archive["end_date"]))} · 참가 {len(participants)}명</p>'
            f'{_participants_table_with_tiers(participants, tiers)}</section>'
        )
    return f'''<section class="archive-section" aria-labelledby="archive-heading">
<p class="archive-eyebrow">KU94 RUN · MONTHLY CHALLENGE</p><h1 id="archive-heading">월별 챌린지 기록</h1>
<p class="archive-intro">진행 중인 달리기와 지난 챌린지 기록을 월별로 확인하세요.</p>
<div class="archive-year-tabs" role="tablist" aria-label="챌린지 연도">{year_tabs}</div>
<div class="archive-tabs" role="tablist" aria-label="월별 챌린지 결과">{"".join(tabs)}</div>
{"".join(panels)}
<script>(()=>{{const years=[...document.querySelectorAll('.archive-year-tab')];const tabs=[...document.querySelectorAll('.archive-tab')];const panels=[...document.querySelectorAll('.archive-panel')];function selectMonth(year,month){{tabs.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.year===year&&t.dataset.month===month)));panels.forEach(p=>p.hidden=!(p.dataset.year===year&&p.id.endsWith('-'+month)))}}function selectYear(year){{years.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.year===year)));tabs.forEach(t=>t.hidden=t.dataset.year!==year);const months=tabs.filter(t=>t.dataset.year===year);const active=months.find(t=>t.getAttribute('aria-selected')==='true')||months[months.length-1];if(active)selectMonth(year,active.dataset.month)}}years.forEach(t=>t.addEventListener('click',()=>selectYear(t.dataset.year)));tabs.forEach(t=>t.addEventListener('click',()=>selectMonth(t.dataset.year,t.dataset.month)));selectYear('{selected_year}')}})();</script></section>'''


def archive_completed_snapshots(
    standings_path: Path = Path("data/standings.json"),
    archive_root: Path = Path("data/archives"),
) -> list[Path]:
    """Persist the last saved standings for past months as permanent month archives."""
    if not standings_path.exists():
        return []
    history = json.loads(standings_path.read_text(encoding="utf-8"))
    if not isinstance(history.get("challenges"), dict):
        return []
    tier_overrides = {}
    registry_root = Path("data/challenges")
    if registry_root.exists():
        for registry_path in registry_root.glob("*.yaml"):
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
            for entry in registry.get("challenges", []):
                if entry.get("achievement_tiers"):
                    tier_overrides[(int(registry.get("year", 0)), int(entry["month"]))] = entry["achievement_tiers"]
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    written = []
    for challenge in history["challenges"].values():
        snapshots = sorted(challenge.get("snapshots", []), key=lambda item: item.get("date", ""))
        if not snapshots:
            continue
        latest = snapshots[-1]
        try:
            snapshot_date = datetime.fromisoformat(str(latest["date"])).date()
        except (KeyError, ValueError):
            continue
        if (snapshot_date.year, snapshot_date.month) >= (today.year, today.month):
            continue
        output = archive_root / str(snapshot_date.year) / f"{snapshot_date.month:02d}.json"
        if output.exists():
            continue
        target = float(challenge.get("target_distance_km") or 0)
        if target <= 0:
            continue
        participants = [
            {"name": person["name"], "rank": int(person["rank"]),
             "distance_km": float(person["distance_km"]), "is_self": bool(person.get("is_self"))}
            for person in latest.get("participants", [])
        ]
        archive = {
            "year": snapshot_date.year,
            "month": snapshot_date.month,
            "title": challenge.get("challenge_name", "Monthly Run Challenge"),
            "end_date": f"최종 기록 · {snapshot_date.isoformat()}",
            "target_distance_km": target,
            "achievement_tiers": tier_overrides.get(
                (snapshot_date.year, snapshot_date.month), {"rabbit": target}
            ),
            "participants": participants,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(output)
    return written


def render_archive_pages(data_root: Path = Path("data/archives"), site_dir: Path = Path("site")) -> None:
    """Render direct-link detail pages and an index for archived results by year."""
    archives = load_archives(data_root)
    history_dir = site_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[int, list[dict]] = {}
    for archive in archives:
        grouped.setdefault(int(archive["year"]), []).append(archive)
        year = int(archive["year"])
        month = int(archive["month"])
        title = escape(str(archive["title"]))
        participants = _visible_participants(archive["participants"])
        tiers = archive.get("achievement_tiers") or {"rabbit": archive["target_distance_km"]}
        page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} 결과</title><style>body{{font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:900px;margin:30px auto;padding:0 16px;color:#2b1b20;background:#f7f2ef}}table{{width:100%;border-collapse:collapse;background:#fffdfb}}th,td{{padding:9px;border-bottom:1px solid #eadfe2;text-align:left}}th{{color:#806f73;background:#fbf7f4}}td:nth-child(3){{color:#5d1028;font-weight:700}}a{{color:#7a1735}}.achievement-icon{{width:24px;height:24px;vertical-align:middle}}</style>
<p><a href="../index.html">← 최신 리포트</a></p><h1>{year}년 {month}월 · {title}</h1><p>{escape(str(archive["end_date"]))} · 참가 {len(participants)}명</p>
{_participants_table_with_tiers(participants, tiers)}</html>'''
        (history_dir / f"{year}-{month:02d}.html").write_text(page, encoding="utf-8")
    year_links = "".join(
        f'<li><a href="{year}/">{year}년</a> — {len(months)}개월 기록</li>'
        for year, months in sorted(grouped.items(), reverse=True)
    ) or "<li>아직 저장된 월별 결과가 없습니다.</li>"
    for year, months in grouped.items():
        month_links = "".join(
            f'<li><a href="../{year}-{int(item["month"]):02d}.html">{int(item["month"])}월</a> — {escape(str(item["title"]))}</li>'
            for item in sorted(months, key=lambda item: int(item["month"]), reverse=True)
        )
        year_page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{year} 월별 결과</title>
<style>body{{font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:780px;margin:40px auto;padding:0 18px;color:#2b1b20;background:#f7f2ef}}li{{margin:14px 0}}a{{color:#7a1735}}</style>
<p><a href="index.html">← 연도 목록</a></p><h1>{year}년 월별 챌린지 결과</h1><ul>{month_links}</ul></html>'''
        (history_dir / str(year)).mkdir(parents=True, exist_ok=True)
        (history_dir / str(year) / "index.html").write_text(year_page, encoding="utf-8")
    index = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>챌린지 연도별 결과</title>
<style>body{{font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:780px;margin:40px auto;padding:0 18px;color:#2b1b20;background:#f7f2ef}}li{{margin:14px 0}}a{{color:#7a1735}}</style>
<p><a href="../index.html">← 최신 리포트</a></p><h1>연도별 챌린지 결과</h1><ul>{year_links}</ul></html>'''
    (history_dir / "index.html").write_text(index, encoding="utf-8")
