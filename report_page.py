"""Render and publish-ready package the latest coaching report as a static page."""

from datetime import datetime
from html import escape
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from archive_pages import archive_section_html
from models import ChallengeAnalysisResult


def report_page_url() -> str | None:
    """Return the GitHub Pages URL from configuration or GitHub Actions context."""
    configured_url = os.getenv("REPORT_BASE_URL", "").strip()
    if configured_url:
        return configured_url.rstrip("/") + "/"
    repository = os.getenv("GITHUB_REPOSITORY", "")
    if "/" not in repository:
        return None
    owner, name = repository.split("/", maxsplit=1)
    return f"https://{owner.lower()}.github.io/{name.lower()}/"


def _rank_history_html(result: ChallengeAnalysisResult, history: dict) -> str:
    """Create a responsive SVG rank trend for the leaders and current user."""
    snapshots = history.get("snapshots", [])[-14:]
    if not snapshots:
        return '<p class="muted">순위 기록이 아직 없습니다.</p>'

    latest = snapshots[-1].get("participants", [])
    selected = sorted(latest, key=lambda person: person.get("rank", 10**9))[:6]
    self_person = next((person for person in latest if person.get("is_self")), None)
    if self_person and all(person["name"] != self_person["name"] for person in selected):
        selected.append(self_person)
    if not selected:
        return '<p class="muted">순위 기록이 아직 없습니다.</p>'

    colors = ["#147d64", "#e36b45", "#4376c5", "#b48600", "#8b5cb7", "#278da3", "#c04f78"]
    width, height, left, right, top, bottom = 760, 330, 54, 22, 24, 46
    plot_width, plot_height = width - left - right, height - top - bottom
    selected_names = {person["name"] for person in selected}
    max_rank = max(
        1,
        max(
            int(person.get("rank", 1))
            for snapshot in snapshots
            for person in snapshot.get("participants", [])
            if person.get("name") in selected_names
        ),
    )

    def point(index: int, rank: int) -> tuple[float, float]:
        x = left + (plot_width / max(1, len(snapshots) - 1)) * index
        y = top + ((rank - 1) / max(1, max_rank - 1)) * plot_height
        return x, y

    parts = [f'<svg class="rank-chart" viewBox="0 0 {width} {height}" role="img" aria-label="최근 참가자 순위 변화 그래프">']
    for rank in sorted({1, max_rank} if max_rank > 1 else {1}):
        y = point(0, rank)[1]
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid-line"/>')
        parts.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" class="axis-label">{rank}위</text>')
    for index, snapshot in enumerate(snapshots):
        if len(snapshots) <= 7 or index in {0, len(snapshots) - 1}:
            x, _ = point(index, 1)
            parts.append(f'<text x="{x:.1f}" y="{height-12}" text-anchor="middle" class="axis-label">{escape(snapshot["date"][5:])}</text>')

    legend = []
    for index, current in enumerate(selected):
        name = current["name"]
        color = colors[index % len(colors)]
        coords: list[tuple[float, float]] = []
        for snap_index, snapshot in enumerate(snapshots):
            match = next((p for p in snapshot.get("participants", []) if p.get("name") == name), None)
            if match:
                coords.append(point(snap_index, int(match.get("rank", max_rank))))
        if coords:
            path = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
            parts.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
            parts.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>' for x, y in coords)
            legend.append(f'<span><i style="background:{color}"></i>{escape(name)} {int(current["rank"])}위</span>')
    parts.append("</svg>")
    return f'<div class="chart-wrap">{"".join(parts)}</div><div class="chart-legend">{"".join(legend)}</div>'


def _running_board_html(result: ChallengeAnalysisResult, history: dict) -> str:
    """Build a daily group board and top-ten table from the latest snapshots."""
    snapshots = history.get("snapshots", [])
    latest = snapshots[-1].get("participants", []) if snapshots else []
    if not latest:
        latest = [
            {"name": p.display_name, "rank": p.rank, "distance_km": p.distance_km, "is_self": p.is_self}
            for p in result.participants
        ]
    previous = snapshots[-2].get("participants", []) if len(snapshots) > 1 else []
    previous_distances = {p["name"]: float(p.get("distance_km", 0)) for p in previous}
    increases = [
        (p, max(0.0, float(p.get("distance_km", 0)) - previous_distances[p["name"]]))
        for p in latest if p["name"] in previous_distances
    ]
    active_count = sum(delta >= 0.01 for _, delta in increases)
    biggest = max(increases, key=lambda row: row[1], default=None)
    total_distance = sum(float(p.get("distance_km", 0)) for p in latest)
    finishers = sum(float(p.get("distance_km", 0)) >= result.target_distance_km for p in latest)
    biggest_label = f"{biggest[0]['name']} +{biggest[1]:.2f} km" if biggest and biggest[1] >= 0.01 else "기록 대기 중"
    stats = (
        ("함께 쌓은 거리", f"{total_distance:.1f} km"),
        ("공통 거리 목표 달성", f"{finishers}명"),
        ("직전 기록 대비 증가", f"{active_count}명" if previous else "첫 기록"),
        ("가장 많이 늘어난 거리", biggest_label),
    )
    stat_cards = "".join(
        f'<div class="board-stat"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        for label, value in stats
    )
    rows = []
    for person in sorted(latest, key=lambda row: int(row.get("rank", 10**9)))[:10]:
        distance = float(person.get("distance_km", 0))
        remaining = max(0.0, result.target_distance_km - distance)
        goal_text = "공통 목표 달성 🎉" if remaining <= 0 else f"공통 목표까지 {remaining:.2f} km"
        rows.append(
            f'<tr><td>{int(person.get("rank", 0))}</td><td>{escape(person["name"])}</td>'
            f'<td>{distance:.2f} km</td><td>{goal_text}</td></tr>'
        )
    table = (
        '<div class="table-wrap"><table><thead><tr><th>순위</th><th>러너</th><th>누적</th><th>공통 목표까지</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )
    chart = _rank_history_html(result, history)
    note = "첫 기록을 저장했어요. 다음 일일 실행부터 순위 변화가 이어집니다." if len(snapshots) < 2 else "최근 14회 기록 · 상위 6명과 내 순위를 표시합니다."
    return (
        f'<div class="board-stats">{stat_cards}</div>{table}'
        f'<p class="muted">거리 변화는 직전 일일 기록과 비교합니다.</p>'
        f'<h3 class="chart-heading">순위 변동</h3><p class="muted">{note}</p>{chart}'
    )


def coach_summary_text(result: ChallengeAnalysisResult, report: str) -> str:
    """Build a compact message that fits Kakao's 200-character text template."""
    coach_summary = re.sub(r"(?m)^\s{0,3}#{1,6}\s*|[*_`>\[\]]", "", report)
    coach_summary = " ".join(coach_summary.split()) or "오늘도 무리하지 말고 목표 페이스를 지켜요."
    coach_summary = coach_summary[:90].rstrip()
    summary = (
        f"{result.challenge_name}\n"
        f"누적 {result.my_distance_km:.1f}/{result.target_distance_km:.1f}km(공통 목표) · "
        f"목표까지 {result.remaining_distance_km:.1f}km · {result.remaining_days}일\n"
        f"코칭: {coach_summary}"
    )
    return summary[:200]


def write_kakao_delivery_payload(
    result: ChallengeAnalysisResult,
    report: str,
    output_path: Path = Path("site/kakao_delivery.json"),
) -> Path:
    """Publish the compact Kakao message payload alongside the daily report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "text": coach_summary_text(result, report),
        "report_url": report_page_url() or "https://jinugkim.github.io/ku94run-monthly/",
        "date": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def write_report_page(
    result: ChallengeAnalysisResult,
    report: str,
    output_dir: Path = Path("site"),
    history: dict | None = None,
    public_board_enabled: bool = True,
) -> Path:
    """Write the month-focused challenge archive as the public home page."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    archive_html = archive_section_html(current_result=result)
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#7a1735">
  <title>KU94 RUN | 월별 챌린지 기록</title>
  <style>
    :root {{ color-scheme: light; --ink: #2b1b20; --muted: #806f73; --crimson: #7a1735; --crimson-dark: #5d1028; --line: #eadfe2; --paper: #fffdfb; --bg: #f7f2ef; font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; color: var(--ink); background: radial-gradient(ellipse at 50% 0, #fffaf5 0, var(--bg) 58%); }}
    .topbar {{ height: 66px; display: flex; align-items: center; border-bottom: 1px solid var(--line); background: rgba(255,253,251,.92); }}
    .topbar-inner {{ width: min(100% - 40px, 920px); margin: auto; display: flex; align-items: center; justify-content: space-between; }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 800; letter-spacing: .08em; }}
    .brand-mark {{ color: var(--crimson); font-size: 18px; }}
    .brand-divider {{ width: 1px; height: 22px; background: #d9c8cd; }}
    .brand-note {{ color: var(--muted); font-size: 12px; }}
    main {{ width: min(100% - 40px, 920px); margin: 38px auto 70px; }}
    .archive-section {{ padding: 28px; border: 1px solid var(--line); border-radius: 18px; background: var(--paper); box-shadow: 0 14px 36px rgba(76,25,42,.07); }}
    .archive-eyebrow {{ margin: 0 0 10px; color: var(--crimson); font-size: 12px; font-weight: 800; letter-spacing: .16em; }}
    .archive-section h1 {{ margin: 0; font-size: clamp(28px, 6vw, 42px); letter-spacing: -.05em; }}
    .archive-intro {{ margin: 10px 0 22px; color: var(--muted); font-size: 14px; }}
    .archive-year-tabs, .archive-tabs {{ display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; }}
    .archive-year-tabs::-webkit-scrollbar, .archive-tabs::-webkit-scrollbar {{ display: none; }}
    .archive-year-tabs {{ padding: 2px 0 12px; }}
    .archive-year-tab {{ flex: 0 0 auto; padding: 9px 17px; border: 1px solid var(--line); border-radius: 999px; color: #606b63; background: var(--paper); font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; }}
    .archive-year-tab[aria-selected="true"] {{ border-color: var(--crimson); color: white; background: var(--crimson); box-shadow: 0 5px 14px rgba(122,23,53,.18); }}
    .archive-tabs {{ padding: 2px 0 16px; border-bottom: 1px solid var(--line); }}
    .archive-tab {{ display: inline-flex; align-items: center; gap: 6px; flex: 0 0 auto; padding: 10px 15px; border: 1px solid var(--line); border-radius: 999px; color: #606b63; background: var(--paper); font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; }}
    .archive-tab:hover {{ border-color: #c68d9e; }}
    .archive-tab[aria-selected="true"] {{ border-color: var(--crimson); color: white; background: var(--crimson); }}
    .archive-current-badge {{ padding: 3px 6px; border-radius: 999px; color: var(--crimson-dark); background: #f5e9ed; font-size: 10px; font-weight: 800; }}
    .archive-tab[aria-selected="true"] .archive-current-badge {{ color: var(--crimson-dark); background: #fff; }}
    .archive-tab[hidden], .archive-panel[hidden] {{ display: none; }}
    .archive-panel h3 {{ margin: 20px 0 5px; color: var(--crimson-dark); font-size: 16px; line-height: 1.5; }}
    .archive-panel > .muted {{ margin: 0 0 14px; color: var(--muted); font-size: 13px; }}
    .archive-table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; }}
    .achievement-icon {{ width: 24px; height: 24px; vertical-align: middle; }}
    .archive-table-wrap td:last-child {{ white-space: nowrap; color: var(--crimson-dark); font-size: 13px; font-weight: 700; }}
    .consistency-panel {{ margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--line); }}
    .consistency-panel[hidden] {{ display: none; }}
    .consistency-panel h2 {{ margin: 0 0 6px; color: var(--crimson-dark); font-size: 20px; }}
    .consistency-panel > .archive-intro {{ margin: 0 0 14px; line-height: 1.6; }}
    .points-key {{ margin: -4px 0 12px; color: var(--muted); font-size: 12px; line-height: 1.6; }}
    .consistency-chart-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: #fffdfb; }}
    .consistency-chart {{ display: block; width: 100%; min-width: 620px; height: auto; }}
    .consistency-grid {{ stroke: #eadfe2; stroke-width: 1; }}
    .consistency-axis {{ fill: #806f73; font-size: 11px; }}
    .consistency-legend {{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 12px 2px 16px; color: #5d1028; font-size: 12px; }}
    .consistency-legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .consistency-legend i {{ width: 10px; height: 10px; border-radius: 50%; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 480px; }}
    th, td {{ padding: 11px 13px; border-bottom: 1px solid #f2ebed; text-align: left; }}
    th {{ color: var(--muted); background: #fbf7f4; font-size: 12px; }}
    td:first-child {{ width: 64px; color: #95878b; font-weight: 700; }}
    td:nth-child(2) {{ font-weight: 700; }}
    td:nth-child(3) {{ color: var(--crimson-dark); font-weight: 800; white-space: nowrap; }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    footer {{ margin-top: 18px; color: #8a7c80; text-align: center; font-size: 12px; }}
    @media (max-width: 520px) {{ .topbar {{ height: 58px; }} .topbar-inner, main {{ width: min(100% - 32px, 920px); }} main {{ margin-top: 24px; }} .brand-note {{ display: none; }} .archive-section {{ padding: 19px 16px; border-radius: 15px; }} .archive-intro {{ line-height: 1.6; }} th, td {{ padding: 10px; }} }}
  </style>
</head>
<body>
  <header class="topbar"><div class="topbar-inner"><div class="brand"><span class="brand-mark">KU</span><span>KU94 RUN</span><span class="brand-divider" aria-hidden="true"></span><span class="brand-note">고려대학교 94학번 러닝 모임</span></div></div></header>
  <main>{archive_html}</main>
  <footer>KU94 RUN · 월별 챌린지 아카이브 · 생성 {generated_at}</footer>
</body>
</html>
"""
    page_path = output_dir / "index.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path
