"""Render and publish-ready package the latest coaching report as a static page."""

from __future__ import annotations

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
    """Build an actionable, compact message that fits Kakao's 200-character text template."""
    clean_report = re.sub(r"(?m)^\s{0,3}#{1,6}\s*|[*_`>\[\]]", "", report)
    # Strip unnecessary greetings, introductions, or verbose prefixes
    clean_report = re.sub(r"^(안녕하세요|반갑습니다|안녕)[^.!\n]*[.!\n]\s*", "", clean_report)
    clean_report = re.sub(r"^.*?Run-teller입니다[^.!\n]*[.!\n]\s*", "", clean_report)
    clean_report = re.sub(r"^.*?AI\s*코치[^.!\n]*[.!\n]\s*", "", clean_report)
    clean_report = " ".join(clean_report.split()).strip() or f"오늘 {result.daily_req_for_goal:.1f}km 러닝으로 목표를 채워보세요!"

    challenge_label = result.challenge_name.split(":")[0].strip() if ":" in result.challenge_name else result.challenge_name[:18].strip()
    header = (
        f"[{challenge_label}]\n"
        f"🏃 {result.my_distance_km:.1f}/{result.target_distance_km:.1f}km · 잔여 {result.remaining_days}일\n"
        f"🎯 일일권장: {result.daily_req_for_goal:.1f}km/일 ({result.my_rank}위)"
    )
    budget = 195 - len(header) - 5
    advice = clean_report[:budget].rstrip() if len(clean_report) > budget else clean_report
    return f"{header}\n💡 {advice}"[:200]


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


def _crew_summary_banner_html(result: ChallengeAnalysisResult) -> str:
    """Render a privacy-first crew summary banner showing group distance, participant count, and days left."""
    participants = result.participants or []
    total_distance = sum(float(p.distance_km) for p in participants)
    participant_count = len(participants) or result.total_participants
    finishers = sum(1 for p in participants if float(p.distance_km) >= result.target_distance_km)
    active_runners = [p for p in participants if float(p.distance_km) > 0]
    avg_distance = total_distance / max(1, len(active_runners)) if active_runners else 0.0

    challenge_name = result.challenge_name.strip()
    return f"""<section class="crew-summary-banner" aria-labelledby="crew-summary-title">
  <div class="crew-meta-row">
    <span class="crew-live-pill"><span class="pulse-dot" aria-hidden="true"></span>진행 중</span>
    <span class="crew-days-left">남은 기간 <strong>{result.remaining_days}일</strong> <small>(D-{result.remaining_days})</small></span>
  </div>
  <h2 id="crew-summary-title" class="crew-challenge-title">{escape(challenge_name)}</h2>

  <div class="crew-stat-grid">
    <div class="crew-stat-card">
      <div class="crew-stat-icon" aria-hidden="true">🏃</div>
      <div class="crew-stat-body">
        <span class="crew-stat-label">함께 달린 거리</span>
        <span class="crew-stat-value"><strong>{total_distance:.1f}</strong> <small>km</small></span>
      </div>
    </div>
    <div class="crew-stat-card">
      <div class="crew-stat-icon" aria-hidden="true">👥</div>
      <div class="crew-stat-body">
        <span class="crew-stat-label">참여 러너</span>
        <span class="crew-stat-value"><strong>{participant_count}</strong> <small>명</small></span>
      </div>
    </div>
    <div class="crew-stat-card">
      <div class="crew-stat-icon" aria-hidden="true">🎯</div>
      <div class="crew-stat-body">
        <span class="crew-stat-label">공통 목표 달성</span>
        <span class="crew-stat-value"><strong>{finishers}</strong> <small>명 완주 🎉</small></span>
      </div>
    </div>
    <div class="crew-stat-card">
      <div class="crew-stat-icon" aria-hidden="true">⚡</div>
      <div class="crew-stat-body">
        <span class="crew-stat-label">1인 평균 거리</span>
        <span class="crew-stat-value"><strong>{avg_distance:.1f}</strong> <small>km/인</small></span>
      </div>
    </div>
  </div>
</section>"""


def write_report_page(
    result: ChallengeAnalysisResult,
    report: str,
    output_dir: Path = Path("site"),
    history: dict | None = None,
    public_board_enabled: bool = True,
) -> Path:
    """Write the mobile-optimized, dark-mode ready challenge report as the home page."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    crew_banner_html = _crew_summary_banner_html(result)
    archive_html = archive_section_html(current_result=result)

    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#7a1735" id="meta-theme-color">
  <meta name="color-scheme" content="light dark">
  <title>KU94 RUN | 챌린지 리포트 & 기록</title>
  <script>
    (function() {{
      try {{
        var saved = localStorage.getItem('ku94run_theme');
        if (saved) {{
          document.documentElement.setAttribute('data-theme', saved);
        }} else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
          document.documentElement.setAttribute('data-theme', 'dark');
        }}
      }} catch(e) {{}}
    }})();
  </script>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f8f5f2;
      --bg-gradient: radial-gradient(ellipse at 50% 0%, #ffffff 0%, #f6f1ee 70%);
      --paper: #ffffff;
      --paper-subtle: #fbf8f6;
      --ink: #2b1b20;
      --ink-secondary: #57484d;
      --muted: #847479;
      --crimson: #7a1735;
      --crimson-dark: #580d22;
      --crimson-light: #fcedf1;
      --crimson-border: #f0cdd6;
      --line: #eadfe2;
      --topbar-bg: rgba(255, 255, 255, 0.88);
      --card-shadow: 0 12px 32px rgba(76, 25, 42, 0.06);
      font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }}

    [data-theme="dark"] {{
      --bg: #121013;
      --bg-gradient: radial-gradient(ellipse at 50% 0%, #1e1920 0%, #121013 70%);
      --paper: #1c181e;
      --paper-subtle: #241f27;
      --ink: #f5eff2;
      --ink-secondary: #c9bdc2;
      --muted: #9e8e94;
      --crimson: #ff5e84;
      --crimson-dark: #ffa1b7;
      --crimson-light: #381622;
      --crimson-border: #5e1c31;
      --line: #2e2832;
      --topbar-bg: rgba(26, 22, 28, 0.88);
      --card-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
    }}

    @media (prefers-color-scheme: dark) {{
      :root:not([data-theme="light"]) {{
        --bg: #121013;
        --bg-gradient: radial-gradient(ellipse at 50% 0%, #1e1920 0%, #121013 70%);
        --paper: #1c181e;
        --paper-subtle: #241f27;
        --ink: #f5eff2;
        --ink-secondary: #c9bdc2;
        --muted: #9e8e94;
        --crimson: #ff5e84;
        --crimson-dark: #ffa1b7;
        --crimson-light: #381622;
        --crimson-border: #5e1c31;
        --line: #2e2832;
        --topbar-bg: rgba(26, 22, 28, 0.88);
        --card-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
      }}
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: var(--bg-gradient);
      padding-bottom: max(30px, env(safe-area-inset-bottom));
      line-height: 1.5;
    }}

    .topbar {{
      position: sticky;
      top: 0;
      z-index: 100;
      height: 62px;
      display: flex;
      align-items: center;
      border-bottom: 1px solid var(--line);
      background: var(--topbar-bg);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
    }}
    .topbar-inner {{
      width: min(100% - 32px, 920px);
      margin: auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 9px;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: .06em;
      color: var(--ink);
      text-decoration: none;
    }}
    .brand-mark {{
      color: var(--crimson);
      font-size: 19px;
      font-weight: 900;
    }}
    .brand-divider {{
      width: 1px;
      height: 18px;
      background: var(--line);
    }}
    .brand-note {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 500;
    }}

    /* Theme Toggle */
    .theme-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--paper-subtle);
      color: var(--ink);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all .2s ease;
      touch-action: manipulation;
    }}
    .theme-toggle:hover {{
      border-color: var(--crimson);
      color: var(--crimson);
    }}

    main {{
      width: min(100% - 32px, 920px);
      margin: 24px auto 60px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}

    /* Crew Summary Banner */
    .crew-summary-banner {{
      padding: 24px 26px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: var(--paper);
      box-shadow: var(--card-shadow);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .crew-meta-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .crew-live-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--crimson-light);
      color: var(--crimson-dark);
      border: 1px solid var(--crimson-border);
      font-size: 12px;
      font-weight: 700;
    }}
    .pulse-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--crimson);
      animation: pulse-ring 1.8s infinite;
    }}
    @keyframes pulse-ring {{
      0% {{ transform: scale(0.9); opacity: 0.8; }}
      50% {{ transform: scale(1.3); opacity: 1; }}
      100% {{ transform: scale(0.9); opacity: 0.8; }}
    }}
    .crew-days-left {{
      font-size: 13px;
      color: var(--muted);
    }}
    .crew-days-left strong {{
      color: var(--crimson);
      font-weight: 800;
    }}
    .crew-days-left small {{
      color: var(--muted);
      font-size: 12px;
    }}
    .crew-challenge-title {{
      margin: 0;
      font-size: clamp(18px, 4vw, 24px);
      font-weight: 800;
      letter-spacing: -.03em;
      color: var(--ink);
      line-height: 1.35;
    }}
    .crew-stat-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
    }}
    .crew-stat-card {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      border-radius: 14px;
      background: var(--paper-subtle);
      border: 1px solid var(--line);
    }}
    .crew-stat-icon {{
      font-size: 22px;
      flex-shrink: 0;
    }}
    .crew-stat-body {{
      display: flex;
      flex-direction: column;
      min-width: 0;
    }}
    .crew-stat-label {{
      font-size: 11px;
      color: var(--muted);
      font-weight: 600;
      white-space: nowrap;
    }}
    .crew-stat-value {{
      font-size: 15px;
      color: var(--ink);
      font-weight: 500;
      white-space: nowrap;
    }}
    .crew-stat-value strong {{
      font-size: 18px;
      font-weight: 800;
      color: var(--crimson-dark);
    }}
    .crew-stat-value small {{
      font-size: 12px;
      color: var(--muted);
    }}

    /* Archive Section */
    .archive-section {{
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: var(--paper);
      box-shadow: var(--card-shadow);
    }}
    .archive-eyebrow {{
      margin: 0 0 8px;
      color: var(--crimson);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .14em;
    }}
    .archive-section h1 {{
      margin: 0;
      font-size: clamp(24px, 5vw, 36px);
      letter-spacing: -.04em;
      color: var(--ink);
    }}
    .archive-intro {{
      margin: 8px 0 20px;
      color: var(--muted);
      font-size: 14px;
    }}
    .archive-year-tabs, .archive-tabs {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      scrollbar-width: none;
      -webkit-overflow-scrolling: touch;
      padding-bottom: 8px;
    }}
    .archive-year-tabs::-webkit-scrollbar, .archive-tabs::-webkit-scrollbar {{
      display: none;
    }}
    .archive-year-tab {{
      flex: 0 0 auto;
      padding: 8px 16px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: var(--paper-subtle);
      font: inherit;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      touch-action: manipulation;
    }}
    .archive-year-tab[aria-selected="true"] {{
      border-color: var(--crimson);
      color: white;
      background: var(--crimson);
      box-shadow: 0 4px 12px rgba(122,23,53,.22);
    }}
    .archive-tabs {{
      padding: 4px 0 16px;
      border-bottom: 1px solid var(--line);
    }}
    .archive-tab {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex: 0 0 auto;
      padding: 9px 15px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--ink-secondary);
      background: var(--paper-subtle);
      font: inherit;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      touch-action: manipulation;
    }}
    .archive-tab:hover {{
      border-color: var(--crimson);
    }}
    .archive-tab[aria-selected="true"] {{
      border-color: var(--crimson);
      color: white;
      background: var(--crimson);
    }}
    .archive-current-badge {{
      padding: 2px 6px;
      border-radius: 999px;
      color: var(--crimson-dark);
      background: var(--crimson-light);
      font-size: 10px;
      font-weight: 800;
    }}
    .archive-tab[aria-selected="true"] .archive-current-badge {{
      color: var(--crimson);
      background: white;
    }}
    .archive-tab[hidden], .archive-panel[hidden] {{
      display: none;
    }}
    .archive-panel h3 {{
      margin: 20px 0 5px;
      color: var(--crimson-dark);
      font-size: 16px;
      line-height: 1.5;
    }}
    .archive-panel > .muted {{
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 13px;
    }}
    .archive-table-wrap {{
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--paper);
    }}
    .achievement-icon {{
      width: 22px;
      height: 22px;
      vertical-align: middle;
    }}
    .archive-table-wrap td:last-child {{
      white-space: nowrap;
      color: var(--crimson);
      font-size: 13px;
      font-weight: 700;
    }}

    /* Consistency Champion */
    .consistency-panel {{
      margin-top: 28px;
      padding-top: 20px;
      border-top: 1px solid var(--line);
    }}
    .consistency-panel[hidden] {{
      display: none;
    }}
    .consistency-panel h2 {{
      margin: 0 0 6px;
      color: var(--crimson-dark);
      font-size: 20px;
    }}
    .consistency-panel > .archive-intro {{
      margin: 0 0 12px;
      line-height: 1.6;
    }}
    .points-key {{
      margin: -4px 0 14px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }}
    .consistency-chart-wrap {{
      position: relative;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }}
    .consistency-chart {{
      display: block;
      width: 100%;
      min-width: 600px;
      height: auto;
    }}
    .consistency-chart text {{
      font-family: inherit;
    }}
    .consistency-grid {{
      stroke: var(--line);
      stroke-width: 1;
    }}
    .consistency-axis {{
      fill: var(--muted);
      font-size: 11px;
    }}
    .consistency-line, .consistency-projection {{
      stroke-dasharray: 1;
      stroke-dashoffset: 1;
      animation: chart-line-draw 1.1s ease-out forwards;
    }}
    .consistency-point {{
      cursor: crosshair;
      animation: chart-point-in .35s ease-out both;
    }}
    .consistency-point:hover, .consistency-point:focus {{
      r: 6;
      outline: none;
      stroke: var(--paper);
      stroke-width: 2;
    }}
    .consistency-tooltip {{
      position: absolute;
      z-index: 2;
      display: grid;
      gap: 3px;
      min-width: 140px;
      padding: 9px 12px;
      transform: translate(-50%, -112%);
      border: 1px solid var(--line);
      border-radius: 10px;
      color: var(--ink);
      background: var(--paper);
      box-shadow: var(--card-shadow);
      font-size: 12px;
      pointer-events: none;
      white-space: nowrap;
    }}
    .consistency-tooltip[hidden] {{
      display: none;
    }}
    .consistency-tooltip strong {{
      color: var(--crimson-dark);
    }}
    .consistency-tooltip span {{
      color: var(--muted);
    }}
    .consistency-tooltip b {{
      color: var(--crimson);
      font-size: 14px;
    }}
    @keyframes chart-line-draw {{ to {{ stroke-dashoffset: 0; }} }}
    @keyframes chart-point-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .consistency-line, .consistency-projection, .consistency-point {{
        animation: none;
        stroke-dashoffset: 0;
      }}
    }}
    .consistency-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      margin: 12px 2px 16px;
      color: var(--ink-secondary);
      font-size: 12px;
    }}
    .consistency-legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .consistency-legend i {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}

    /* Podium & Hall of Fame */
    .podium-section {{
      margin: 16px 0 20px;
      padding: 20px 22px;
      background: var(--paper-subtle);
      border: 1px solid var(--line);
      border-radius: 18px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .podium-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .podium-badge {{
      font-size: 14px;
      font-weight: 800;
      color: var(--crimson-dark);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .podium-sub {{
      font-size: 12px;
      color: var(--muted);
    }}
    .podium-grid {{
      display: grid;
      grid-template-columns: 1fr 1.15fr 1fr;
      align-items: end;
      gap: 12px;
    }}
    .podium-card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 12px 14px;
      text-align: center;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      position: relative;
      box-shadow: var(--card-shadow);
      transition: transform .2s ease;
    }}
    .podium-first {{
      border-color: #b08a42;
      background: linear-gradient(180deg, rgba(176, 138, 66, 0.08) 0%, var(--paper) 100%);
      padding-top: 22px;
      padding-bottom: 18px;
      transform: translateY(-6px);
    }}
    [data-theme="dark"] .podium-first {{
      background: linear-gradient(180deg, rgba(229, 184, 66, 0.12) 0%, var(--paper) 100%);
      border-color: #d4af37;
    }}
    .podium-second {{
      border-color: #94a3b8;
    }}
    .podium-third {{
      border-color: #c07a50;
    }}
    .podium-icon {{
      font-size: 26px;
      line-height: 1;
      margin-bottom: 2px;
      filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.12));
    }}
    .podium-first .podium-icon {{
      font-size: 30px;
    }}
    .podium-rank-tag {{
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .04em;
      color: var(--muted);
    }}
    .podium-first .podium-rank-tag {{
      color: #b08a42;
    }}
    [data-theme="dark"] .podium-first .podium-rank-tag {{
      color: #e5b842;
    }}
    .podium-second .podium-rank-tag {{
      color: #64748b;
    }}
    [data-theme="dark"] .podium-second .podium-rank-tag {{
      color: #94a3b8;
    }}
    .podium-third .podium-rank-tag {{
      color: #9c5a32;
    }}
    [data-theme="dark"] .podium-third .podium-rank-tag {{
      color: #c07a50;
    }}
    .podium-name {{
      font-size: 15px;
      font-weight: 800;
      color: var(--ink);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
    }}
    .podium-first .podium-name {{
      font-size: 17px;
      color: var(--crimson-dark);
    }}
    .podium-score {{
      font-size: 13px;
      font-weight: 700;
      color: var(--ink-secondary);
    }}
    .podium-score small {{
      font-size: 11px;
      color: var(--muted);
      font-weight: 500;
    }}
    .annual-milestone-bar {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      padding-top: 14px;
      border-top: 1px dashed var(--line);
    }}
    .milestone-item {{
      display: flex;
      flex-direction: column;
      gap: 3px;
      text-align: center;
    }}
    .milestone-item span {{
      font-size: 11px;
      color: var(--muted);
      font-weight: 600;
    }}
    .milestone-item strong {{
      font-size: 14px;
      color: var(--ink);
      font-weight: 800;
    }}
    .milestone-item strong small {{
      display: block;
      font-size: 10px;
      color: var(--muted);
      font-weight: 500;
    }}

    /* Tables */
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 440px;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
    }}
    th {{
      color: var(--muted);
      background: var(--paper-subtle);
      font-size: 12px;
      font-weight: 700;
    }}
    td:first-child {{
      width: 58px;
      color: var(--muted);
      font-weight: 700;
    }}
    td:nth-child(2) {{
      font-weight: 700;
      color: var(--ink);
    }}
    td:nth-child(3) {{
      color: var(--crimson-dark);
      font-weight: 800;
      white-space: nowrap;
    }}
    tbody tr:last-child td {{
      border-bottom: 0;
    }}
    tbody tr:hover td {{
      background: var(--paper-subtle);
    }}

    footer {{
      margin-top: 10px;
      color: var(--muted);
      text-align: center;
      font-size: 12px;
      line-height: 1.6;
    }}

    /* Mobile Enhancements */
    @media (max-width: 680px) {{
      .topbar {{
        height: 56px;
      }}
      .topbar-inner, main {{
        width: min(100% - 24px, 920px);
      }}
      main {{
        margin: 16px auto 40px;
        gap: 16px;
      }}
      .brand-note {{
        display: none;
      }}
      .brand-divider {{
        display: none;
      }}
      .crew-summary-banner {{
        padding: 18px 16px;
        border-radius: 16px;
        gap: 14px;
      }}
      .crew-challenge-title {{
        font-size: 18px;
      }}
      .crew-stat-grid {{
        grid-template-columns: 1fr 1fr;
        gap: 8px;
      }}
      .crew-stat-card {{
        padding: 10px 12px;
        gap: 10px;
        border-radius: 12px;
      }}
      .crew-stat-icon {{
        font-size: 20px;
      }}
      .crew-stat-value strong {{
        font-size: 16px;
      }}
      .crew-stat-label {{
        font-size: 10.5px;
      }}
      .podium-section {{
        padding: 16px 14px;
        border-radius: 14px;
        gap: 12px;
      }}
      .podium-grid {{
        gap: 8px;
      }}
      .podium-card {{
        padding: 12px 6px 10px;
      }}
      .podium-name {{
        font-size: 13.5px;
      }}
      .podium-first .podium-name {{
        font-size: 15px;
      }}
      .podium-score {{
        font-size: 11.5px;
      }}
      .annual-milestone-bar {{
        grid-template-columns: 1fr;
        gap: 8px;
      }}
      .milestone-item {{
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
      }}
      .archive-section {{
        padding: 18px 16px;
        border-radius: 16px;
      }}
      .archive-section h1 {{
        font-size: 22px;
      }}
      .archive-year-tab, .archive-tab {{
        padding: 8px 13px;
        font-size: 13px;
      }}
      th, td {{
        padding: 10px 10px;
        font-size: 13px;
      }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <a href="#" class="brand">
        <span class="brand-mark">KU</span>
        <span>KU94 RUN</span>
        <span class="brand-divider" aria-hidden="true"></span>
        <span class="brand-note">고려대학교 94학번 러닝 크루</span>
      </a>
      <button class="theme-toggle" id="theme-toggle" type="button" aria-label="다크 모드 전환">
        <span class="theme-icon" aria-hidden="true">🌓</span>
        <span class="theme-label">테마</span>
      </button>
    </div>
  </header>
  <main>
    {crew_banner_html}
    {archive_html}
  </main>
  <footer>
    KU94 RUN · 월별 챌린지 리포트 & 아카이브<br>
    최근 데이터 수집: {generated_at}
  </footer>

  <script>
    (() => {{
      const toggle = document.getElementById('theme-toggle');
      if (!toggle) return;
      const root = document.documentElement;
      const icon = toggle.querySelector('.theme-icon');
      const label = toggle.querySelector('.theme-label');
      const metaTheme = document.getElementById('meta-theme-color');

      function getEffectiveTheme() {{
        const explicit = root.getAttribute('data-theme');
        if (explicit === 'dark' || explicit === 'light') return explicit;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }}

      function updateUI(theme) {{
        if (theme === 'dark') {{
          if (icon) icon.textContent = '☀️';
          if (label) label.textContent = '라이트';
          if (metaTheme) metaTheme.setAttribute('content', '#1c181e');
        }} else {{
          if (icon) icon.textContent = '🌙';
          if (label) label.textContent = '다크';
          if (metaTheme) metaTheme.setAttribute('content', '#7a1735');
        }}
      }}

      updateUI(getEffectiveTheme());

      toggle.addEventListener('click', () => {{
        const next = getEffectiveTheme() === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        try {{ localStorage.setItem('ku94run_theme', next); }} catch (e) {{}}
        updateUI(next);
      }});

      if (window.matchMedia) {{
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {{
          if (!localStorage.getItem('ku94run_theme')) {{
            updateUI(e.matches ? 'dark' : 'light');
          }}
        }});
      }}
    }})();
  </script>
</body>
</html>
"""
    page_path = output_dir / "index.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path
