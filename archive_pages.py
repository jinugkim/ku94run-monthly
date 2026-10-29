"""Render public pages for archived monthly challenge results."""

from html import escape
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def load_archives(data_root: Path = Path("data/archives")) -> list[dict]:
    archives = []
    if data_root.exists():
        for path in sorted(data_root.glob("*/[0-9][0-9].json")):
            archives.append(json.loads(path.read_text(encoding="utf-8")))
    return sorted(archives, key=lambda item: (int(item["year"]), int(item["month"])))


def _participants_table(participants: list[dict], target_distance_km: float) -> str:
    rows = "".join(
        f'<tr><td>{int(p["rank"])}</td><td>{escape(str(p["name"]))}</td>'
        f'<td>{float(p["distance_km"]):.2f} km</td>'
        f'<td>{"달성" if float(p["distance_km"]) >= target_distance_km else ""}</td></tr>'
        for p in sorted(participants, key=lambda person: int(person["rank"]))
    )
    return (
        '<div class="archive-table-wrap"><table><thead><tr><th>순위</th><th>러너</th>'
        f'<th>거리</th><th>목표 ({target_distance_km:g} km)</th></tr></thead><tbody>{rows}</tbody></table></div>'
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
            "participants": [
                {"name": participant.display_name, "rank": participant.rank,
                 "distance_km": round(participant.distance_km, 2)}
                for participant in current_result.participants
            ],
            "is_current": True,
        })
    archives = sorted(archives, key=lambda item: (int(item["year"]), int(item["month"])))
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
        target = float(archive["target_distance_km"])
        participants = archive["participants"]
        panels.append(
            f'<section class="archive-panel" id="{panel_id}" role="tabpanel" aria-labelledby="{tab_id}" '
            f'data-year="{year}"{"" if selected else " hidden"}>'
            f'<h3>{year}년 {month}월 · {title}</h3>'
            f'<p class="muted">{escape(str(archive["end_date"]))} · 참가 {len(participants)}명</p>'
            f'{_participants_table(participants, target)}</section>'
        )
    return f'''<section class="archive-section" aria-labelledby="archive-heading">
<p class="archive-eyebrow">KU94 RUN · MONTHLY CHALLENGE</p><h1 id="archive-heading">월별 챌린지 기록</h1>
<p class="archive-intro">진행 중인 달리기와 지난 챌린지 기록을 월별로 확인하세요.</p>
<div class="archive-year-tabs" role="tablist" aria-label="챌린지 연도">{year_tabs}</div>
<div class="archive-tabs" role="tablist" aria-label="월별 챌린지 결과">{"".join(tabs)}</div>
{"".join(panels)}
<script>(()=>{{const years=[...document.querySelectorAll('.archive-year-tab')];const tabs=[...document.querySelectorAll('.archive-tab')];const panels=[...document.querySelectorAll('.archive-panel')];function selectMonth(year,month){{tabs.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.year===year&&t.dataset.month===month)));panels.forEach(p=>p.hidden=!(p.dataset.year===year&&p.id.endsWith('-'+month)))}}function selectYear(year){{years.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.year===year)));tabs.forEach(t=>t.hidden=t.dataset.year!==year);const months=tabs.filter(t=>t.dataset.year===year);const active=months.find(t=>t.getAttribute('aria-selected')==='true')||months[months.length-1];if(active)selectMonth(year,active.dataset.month)}}years.forEach(t=>t.addEventListener('click',()=>selectYear(t.dataset.year)));tabs.forEach(t=>t.addEventListener('click',()=>selectMonth(t.dataset.year,t.dataset.month)));selectYear('{selected_year}')}})();</script></section>'''


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
        participants = archive["participants"]
        target = float(archive["target_distance_km"])
        page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} 결과</title><style>body{{font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:900px;margin:30px auto;padding:0 16px;color:#2b1b20;background:#f7f2ef}}table{{width:100%;border-collapse:collapse;background:#fffdfb}}th,td{{padding:9px;border-bottom:1px solid #eadfe2;text-align:left}}th{{color:#806f73;background:#fbf7f4}}td:nth-child(3){{color:#5d1028;font-weight:700}}a{{color:#7a1735}}</style>
<p><a href="../index.html">← 최신 리포트</a></p><h1>{year}년 {month}월 · {title}</h1><p>최종 기록일: {escape(str(archive["end_date"]))} · 공통 목표: {target:g} km · 참가 {len(participants)}명</p>
{_participants_table(participants, target)}</html>'''
        (history_dir / f"{year}-{month:02d}.html").write_text(page, encoding="utf-8")
    year_links = "".join(
        f'<li><a href="{year}/">{year}년</a> — {len(months)}개월 기록</li>'
        for year, months in sorted(grouped.items(), reverse=True)
    ) or "<li>아직 저장된 월별 결과가 없습니다.</li>"
    for year, months in grouped.items():
        month_links = "".join(
            f'<li><a href="../{year}-{int(item["month"]):02d}.html">{int(item["month"])}월</a> — {escape(str(item["title"]))}</li>'
            for item in sorted(months, key=lambda item: int(item["month"]))
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
