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


def _consistency_champion_html(
    archives: list[dict], year: int, current_year: int, selected: bool
) -> str:
    """Render cumulative monthly points and a simple December pace projection."""
    completed = sorted(
        (archive for archive in archives
         if int(archive["year"]) == year and not archive.get("is_current")),
        key=lambda archive: int(archive["month"]),
    )
    if not completed:
        return (
            f'<section class="consistency-panel" data-year="{year}"{"" if selected else " hidden"}><h2>Consistency Champion</h2>'
            '<p class="archive-intro">확정된 월별 결과가 모이면 누적 포인트 그래프가 표시됩니다.</p></section>'
        )

    points_by_month: dict[int, dict[str, int]] = {}
    month_totals: dict[str, int] = {}
    latest_month = max(int(archive["month"]) for archive in completed)
    rank_points = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4}
    for archive in completed:
        month = int(archive["month"])
        this_month: dict[str, int] = {}
        for person in _visible_participants(archive["participants"]):
            rank = int(person["rank"])
            score = rank_points.get(rank, 2 if rank <= 10 else 1)
            name = str(person["name"])
            this_month[name] = this_month.get(name, 0) + score
            month_totals[name] = month_totals.get(name, 0) + score
        points_by_month[month] = this_month

    forecast = year == current_year and latest_month < 12
    estimates = {
        name: round(total * 12 / latest_month) if forecast else total
        for name, total in month_totals.items()
    }
    leaders = sorted(
        month_totals,
        key=lambda name: (-estimates[name], -month_totals[name], name.casefold()),
    )[:5]
    max_value = max([*month_totals.values(), *(estimates[name] for name in leaders)], default=1)
    max_value = max(10, max_value * 1.15)
    width, height, left, right, top, bottom = 760, 300, 48, 18, 20, 38
    plot_width, plot_height = width - left - right, height - top - bottom

    def point(month: int, value: float) -> tuple[float, float]:
        return left + (month - 1) * plot_width / 11, top + (max_value - value) * plot_height / max_value

    svg = [f'<svg class="consistency-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Consistency Champion 월별 누적 포인트 그래프">']
    for value in (0, round(max_value)):
        _, y = point(1, value)
        svg.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="consistency-grid"/>')
        svg.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" class="consistency-axis">{value}점</text>')
    for month in (1, 3, 6, 9, 12):
        x, _ = point(month, 0)
        svg.append(f'<text x="{x:.1f}" y="{height-10}" text-anchor="middle" class="consistency-axis">{month}월</text>')

    colors = ["#7a1735", "#64748b", "#94a3b8", "#b08a42", "#cbd5e1"]
    legends = []
    for index, name in enumerate(leaders):
        color = colors[index % len(colors)]
        running = 0
        actual_points = []
        for month in range(1, latest_month + 1):
            running += points_by_month.get(month, {}).get(name, 0)
            actual_points.append(point(month, running))
        if len(actual_points) > 1:
            coordinates = " ".join(f"{x:.1f},{y:.1f}" for x, y in actual_points)
            svg.append(f'<polyline class="consistency-line" pathLength="1" points="{coordinates}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
        running = 0
        for month, (x, y) in enumerate(actual_points, 1):
            running += points_by_month.get(month, {}).get(name, 0)
            svg.append(
                f'<circle class="consistency-point" cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{color}" '
                f'tabindex="0" role="button" data-name="{escape(name, quote=True)}" '
                f'aria-label="{year}년 {month}월 {escape(name, quote=True)} {running}점" '
                f'data-month="{year}년 {month}월" data-value="{running}" data-label="누적 포인트"/>'
            )
        if forecast:
            start_x, start_y = actual_points[-1]
            end_x, end_y = point(12, estimates[name])
            svg.append(f'<line class="consistency-projection" pathLength="1" x1="{start_x:.1f}" y1="{start_y:.1f}" x2="{end_x:.1f}" y2="{end_y:.1f}" stroke="{color}" stroke-width="2" stroke-dasharray="5 5" opacity=".65"/>')
            svg.append(
                f'<circle class="consistency-point projection-point" cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="{color}" '
                f'tabindex="0" role="button" data-name="{escape(name, quote=True)}" data-month="12월 예상" '
                f'aria-label="12월 예상 {escape(name, quote=True)} {estimates[name]}점" '
                f'data-value="{estimates[name]}" data-label="연말 예상 포인트"/>'
            )
        legends.append(
            f'<span><i style="background:{color}"></i>{escape(name)} · {month_totals[name]}점'
            f'{f" · 연말 예상 {estimates[name]}점" if forecast else ""}</span>'
        )
    svg.append("</svg>")

    table_rows = []
    for rank, name in enumerate(sorted(month_totals, key=lambda person: (-estimates[person], -month_totals[person], person.casefold()))[:10], 1):
        estimate = f"{estimates[name]}점" if forecast else f"{month_totals[name]}점"
        table_rows.append(
            f'<tr><td>{rank}</td><td>{escape(name)}</td><td>{month_totals[name]}점</td><td>{estimate}</td></tr>'
        )
    note = (
        f"1~{latest_month}월 확정 결과 기준 · 현재 월간 평균을 12개월로 환산한 단순 예상입니다."
        if forecast else
        f"1~{latest_month}월 확정 결과 기준 · 연간 최종 포인트입니다."
        if latest_month == 12 else
        f"1~{latest_month}월 저장 결과 기준 · 아직 수집되지 않은 달은 점수에 포함하지 않았습니다."
    )
    if forecast and datetime.now(ZoneInfo("Asia/Seoul")).month > latest_month:
        note += f" 진행 중인 {datetime.now(ZoneInfo('Asia/Seoul')).month}월은 마감 후 반영됩니다."
    return (
        f'<section class="consistency-panel" data-year="{year}"{"" if selected else " hidden"}><h2>Consistency Champion</h2>'
        f'<p class="archive-intro">{note}</p>'
        '<p class="points-key">배점: 1위 10점 · 2위 8점 · 3위 6점 · 4위 5점 · 5위 4점 · 6~10위 2점 · 그 외 참가 1점</p>'
        f'<div class="consistency-chart-wrap">{"".join(svg)}<div class="consistency-tooltip" role="tooltip" hidden></div></div>'
        f'<div class="consistency-legend">{"".join(legends)}</div>'
        f'<div class="archive-table-wrap"><table><thead><tr><th>순위</th><th>러너</th><th>누적</th><th>{"연말 예상" if forecast else "최종 점수"}</th></tr></thead>'
        f'<tbody>{"".join(table_rows)}</tbody></table></div></section>'
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
    year_graphs = "".join(
        _consistency_champion_html(
            archives, year, datetime.now(ZoneInfo("Asia/Seoul")).year,
            selected=year == selected_year,
        )
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
            f'data-year="{year}" data-month="{month:02d}"{"" if year == selected_year else " hidden"}>'
            f'{month}월{current_badge}</button>'
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
{"".join(year_graphs)}
<script>(()=>{{const years=[...document.querySelectorAll('.archive-year-tab')];const tabs=[...document.querySelectorAll('.archive-tab')];const panels=[...document.querySelectorAll('.archive-panel')];const charts=[...document.querySelectorAll('.consistency-panel')];function selectMonth(year,month){{tabs.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.year===year&&t.dataset.month===month)));panels.forEach(p=>p.hidden=!(p.dataset.year===year&&p.id.endsWith('-'+month)))}}function selectYear(year){{years.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.year===year)));tabs.forEach(t=>t.hidden=t.dataset.year!==year);charts.forEach(p=>p.hidden=p.dataset.year!==year);const months=tabs.filter(t=>t.dataset.year===year);const active=months.find(t=>t.getAttribute('aria-selected')==='true')||months[months.length-1];if(active)selectMonth(year,active.dataset.month)}}years.forEach(t=>t.addEventListener('click',()=>selectYear(t.dataset.year)));tabs.forEach(t=>t.addEventListener('click',()=>selectMonth(t.dataset.year,t.dataset.month)));document.querySelectorAll('.consistency-chart-wrap').forEach(wrap=>{{const tip=wrap.querySelector('.consistency-tooltip');const show=(point,event)=>{{const box=wrap.getBoundingClientRect();const name=document.createElement('strong');name.textContent=point.dataset.name;const detail=document.createElement('span');detail.textContent=`${{point.dataset.month}} · ${{point.dataset.label}}`;const value=document.createElement('b');value.textContent=`${{point.dataset.value}}점`;tip.replaceChildren(name,detail,value);tip.hidden=false;const target=event.type.startsWith('pointer')?event.target.getBoundingClientRect():point.getBoundingClientRect();tip.style.left=`${{target.left-box.left+wrap.scrollLeft+target.width/2}}px`;tip.style.top=`${{target.top-box.top}}px`}};wrap.querySelectorAll('.consistency-point').forEach(point=>{{point.addEventListener('pointerenter',event=>show(point,event));point.addEventListener('focus',event=>show(point,event));point.addEventListener('pointerleave',()=>tip.hidden=true);point.addEventListener('blur',()=>tip.hidden=true)}})}});selectYear('{selected_year}')}})();</script></section>'''


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
