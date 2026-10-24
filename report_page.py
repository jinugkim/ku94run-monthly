"""Render and publish-ready package the latest coaching report as a static page."""

from datetime import datetime
from html import escape
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import bleach
import markdown

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
        ("목표 달성", f"{finishers}명"),
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
        goal_text = "목표 달성 🎉" if remaining <= 0 else f"{remaining:.2f} km 남음"
        rows.append(
            f'<tr><td>{int(person.get("rank", 0))}</td><td>{escape(person["name"])}</td>'
            f'<td>{distance:.2f} km</td><td>{goal_text}</td></tr>'
        )
    table = (
        '<div class="table-wrap"><table><thead><tr><th>순위</th><th>러너</th><th>누적</th><th>목표까지</th></tr></thead>'
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
        f"누적 {result.my_distance_km:.1f}/{result.target_distance_km:.1f}km · "
        f"남은 {result.remaining_distance_km:.1f}km · {result.remaining_days}일\n"
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
        "report_url": report_page_url() or "https://jinugkim.github.io/run-teller/",
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
    """Write a self-contained static HTML report for the current challenge run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    challenge_name = escape(result.challenge_name)
    history = history or ({
        "snapshots": [{
            "date": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
            "participants": [
                {"name": p.display_name, "rank": p.rank, "distance_km": p.distance_km, "is_self": p.is_self}
                for p in result.participants
            ],
        }]
    } if public_board_enabled else {"snapshots": []})
    report_html = markdown.markdown(report, extensions=["extra", "sane_lists"])
    report_html = bleach.clean(
        report_html,
        tags={
            "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4",
            "hr", "li", "ol", "p", "pre", "strong", "table", "tbody", "td",
            "th", "thead", "tr", "ul",
        },
        attributes={"a": ["href", "title"]},
        protocols={"http", "https", "mailto"},
        strip=True,
    )
    generated_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    board_html = (
        '<h2>오늘의 러닝 보드</h2><p class="muted">친구들과 함께 쌓은 챌린지 진행 상황</p>'
        + _running_board_html(result, history)
        if public_board_enabled
        else '<section class="private-note"><h2>러닝 보드 비공개</h2><p class="muted">참가자 기록은 공개하지 않습니다.</p></section>'
    )
    kakao_javascript_key = json.dumps(os.getenv("KAKAO_JS_KEY", ""))
    kakao_share_text = json.dumps(coach_summary_text(result, report), ensure_ascii=False).replace("<", "\\u003c")
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#10231f">
  <title>Run-teller | {challenge_name}</title>
  <style>
    :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f3f5f1; color: #17221e; }}
    body {{ margin: 0; }}
    main {{ max-width: 780px; margin: 0 auto; padding: 32px 18px 56px; }}
    header {{ padding: 26px; border-radius: 20px; background: #10231f; color: #f5f7f2; }}
    header p {{ margin: 8px 0 0; color: #c3d1c8; }}
    h1 {{ margin: 0; font-size: clamp(1.35rem, 4vw, 2rem); }}
    h2 {{ margin: 28px 0 14px; font-size: 1.1rem; }}
    .stats {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }}
    .stat {{ padding: 16px; border-radius: 14px; background: #1c3730; }}
    .label {{ display: block; margin-bottom: 7px; color: #c3d1c8; font-size: .85rem; }}
    .value {{ font-size: 1.35rem; font-weight: 700; }}
    article {{ padding: 22px; border: 1px solid #e0e5df; border-radius: 16px; background: white; line-height: 1.75; overflow-wrap: anywhere; }}
    article > :first-child {{ margin-top: 0; }}
    article > :last-child {{ margin-bottom: 0; }}
    article h1, article h2, article h3, article h4 {{ line-height: 1.4; }}
    article h1 {{ font-size: 1.45rem; }}
    article h2 {{ margin: 1.5em 0 .6em; font-size: 1.25rem; }}
    article h3, article h4 {{ margin: 1.25em 0 .5em; font-size: 1.08rem; }}
    article ul, article ol {{ padding-left: 1.5em; }}
    article blockquote {{ margin: 1em 0; padding: .2em 1em; border-left: 3px solid #9aada2; color: #52635a; }}
    article table {{ width: 100%; border-collapse: collapse; }}
    article th, article td {{ padding: .5em; border: 1px solid #e0e5df; text-align: left; }}
    article code {{ padding: .12em .3em; border-radius: 4px; background: #f0f3ef; }}
    article pre {{ padding: 14px; overflow-x: auto; border-radius: 8px; background: #f0f3ef; }}
    article pre code {{ padding: 0; }}
    article a {{ color: #126a4a; }}
    .board-stats {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 14px 0 20px; }}
    .board-stat {{ display: flex; flex-direction: column; gap: 8px; padding: 16px; border-radius: 14px; background: white; border: 1px solid #e0e5df; }}
    .board-stat span, .muted {{ color: #64736c; font-size: .9rem; }}
    .board-stat strong {{ font-size: 1.2rem; overflow-wrap: anywhere; }}
    .table-wrap {{ overflow-x: auto; border-radius: 12px; background: white; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 440px; }}
    th, td {{ padding: 11px 12px; border-bottom: 1px solid #e8ece8; text-align: left; }}
    th {{ color: #52635a; font-size: .86rem; }}
    .chart-heading {{ margin-top: 30px; }}
    .chart-wrap {{ overflow-x: auto; border: 1px solid #e0e5df; border-radius: 14px; background: white; }}
    .rank-chart {{ display: block; width: 100%; min-width: 520px; height: auto; }}
    .grid-line {{ stroke: #e7ece8; stroke-width: 1; }}
    .axis-label {{ fill: #64736c; font-size: 12px; }}
    .chart-legend {{ display: flex; flex-wrap: wrap; gap: 10px 16px; margin: 12px 2px; color: #52635a; font-size: .88rem; }}
    .chart-legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .chart-legend i {{ width: 10px; height: 10px; border-radius: 50%; }}
    .kakao-action {{ margin-top: 28px; padding: 20px; border: 1px solid #e0e5df; border-radius: 16px; background: white; }}
    .kakao-button {{ padding: 12px 18px; border: 0; border-radius: 10px; background: #fee500; color: #191919; font: inherit; font-weight: 700; cursor: pointer; }}
    .kakao-button:disabled {{ cursor: wait; opacity: .65; }}
    footer {{ margin-top: 18px; color: #64736c; font-size: .82rem; }}
    @media (max-width: 480px) {{ .stats {{ grid-template-columns: 1fr 1fr; }} .stat {{ padding: 12px; }} .value {{ font-size: 1.1rem; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{challenge_name}</h1>
      <p>Run-teller 일일 거리 전략 리포트</p>
      <section class="stats" aria-label="챌린지 진행 상황">
        <div class="stat"><span class="label">누적 거리 / 목표</span><span class="value">{result.my_distance_km:.2f} / {result.target_distance_km:.2f} km</span></div>
        <div class="stat"><span class="label">목표까지 남은 거리</span><span class="value">{result.remaining_distance_km:.2f} km</span></div>
        <div class="stat"><span class="label">남은 기간</span><span class="value">{result.remaining_days}일</span></div>
        <div class="stat"><span class="label">하루 평균 필요 거리</span><span class="value">{result.daily_req_for_goal:.2f} km</span></div>
      </section>
    </header>
    <h2>오늘의 코칭</h2>
    <article>{report_html}</article>
    {board_html}
    <section class="kakao-action" aria-labelledby="kakao-heading">
      <h2 id="kakao-heading">러닝 코치 요약 공유</h2>
      <p class="muted">누적 거리와 남은 목표, 코칭 한 줄을 카카오톡에 공유합니다.</p>
      <button class="kakao-button" id="kakao-send" type="button">코치 요약 공유하기</button>
    </section>
    <footer>생성 시각: {generated_at}. 거리 목표가 우선이며 페이스는 사용자가 직접 관리합니다.</footer>
  </main>
  <script src="https://t1.kakaocdn.net/kakao_js_sdk/2.8.4/kakao.min.js" integrity="sha384-BGX7Wb16GmRFagri4bLJV2DgipVZaU2AI812GZtHtHzzDQJnfHasDXN5houxv45w" crossorigin="anonymous"></script>
  <script>
    (() => {{
      const JAVASCRIPT_KEY = {kakao_javascript_key};
      if (!window.Kakao) {{
        alert('카카오 SDK를 불러오지 못했습니다. 네트워크 연결을 확인해 주세요.');
        return;
      }}
      if (!JAVASCRIPT_KEY) {{
        alert('카카오 JavaScript 키가 설정되지 않았습니다. GitHub Actions secret KAKAO_JS_KEY를 확인해 주세요.');
        return;
      }}
      if (!Kakao.isInitialized()) Kakao.init(JAVASCRIPT_KEY);

      const button = document.getElementById('kakao-send');
      button.addEventListener('click', () => {{
        const reportUrl = window.location.href.split('#')[0];
        try {{
          Kakao.Share.sendDefault({{
            objectType: 'text',
            text: {kakao_share_text},
            link: {{ webUrl: reportUrl, mobileWebUrl: reportUrl }}
          }});
        }} catch (error) {{
          console.error('Kakao share error:', error);
          alert('카카오톡 공유를 시작하지 못했습니다. 앱 키와 도메인 설정을 확인해 주세요.');
        }}
      }});
    }})();
  </script>
</body>
</html>
"""
    page_path = output_dir / "index.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path
