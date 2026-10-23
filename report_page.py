"""Render and publish-ready package the latest coaching report as a static page."""

from datetime import datetime
from html import escape
import json
import os
from pathlib import Path
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


def write_report_page(result: ChallengeAnalysisResult, report: str, output_dir: Path = Path("site")) -> Path:
    """Write a self-contained static HTML report for the current challenge run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    challenge_name = escape(result.challenge_name)
    participant_data = json.dumps(
        [
            {
                "name": participant.display_name,
                "rank": participant.rank,
                "distance": round(participant.distance_km, 2),
            }
            for participant in result.participants
        ],
        ensure_ascii=False,
    ).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
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
    .search-box {{ margin: 12px 0 16px; }}
    .search-box input {{ box-sizing: border-box; width: 100%; padding: 13px 14px; border: 1px solid #cbd5ce; border-radius: 10px; font: inherit; }}
    .participant-result {{ margin-top: 10px; padding: 16px; border: 1px solid #e0e5df; border-radius: 12px; background: white; }}
    .participant-result h3 {{ margin: 0 0 8px; }}
    .participant-result p {{ margin: 4px 0; }}
    .muted {{ color: #64736c; }}
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
    <h2>참가자 검색</h2>
    <p class="muted">이름을 입력하면 해당 참가자의 챌린지 거리 현황을 볼 수 있습니다.</p>
    <label class="search-box"><span class="muted">참가자 이름</span><input id="participant-search" type="search" autocomplete="off" placeholder="이름 일부를 입력하세요"></label>
    <div id="participant-results" aria-live="polite" class="muted">검색어를 입력하세요.</div>
    <footer>생성 시각: {generated_at}. 거리 목표가 우선이며 페이스는 사용자가 직접 관리합니다.</footer>
  </main>
  <script id="participant-data" type="application/json">{participant_data}</script>
  <script>
    const participants = JSON.parse(document.getElementById("participant-data").textContent);
    const searchInput = document.getElementById("participant-search");
    const results = document.getElementById("participant-results");
    const targetKm = {result.target_distance_km};
    const remainingDays = {result.remaining_days};
    function addText(parent, tag, text, className) {{
      const node = document.createElement(tag);
      node.textContent = text;
      if (className) node.className = className;
      parent.appendChild(node);
    }}
    searchInput.addEventListener("input", () => {{
      const query = searchInput.value.trim().toLocaleLowerCase("ko-KR");
      results.replaceChildren();
      if (!query) {{ results.textContent = "검색어를 입력하세요."; return; }}
      const matches = participants.filter((person) => person.name.toLocaleLowerCase("ko-KR").includes(query));
      if (!matches.length) {{ results.textContent = "일치하는 참가자가 없습니다."; return; }}
      matches.slice(0, 30).forEach((person) => {{
        const card = document.createElement("section");
        card.className = "participant-result";
        const remaining = Math.max(0, targetKm - person.distance);
        addText(card, "h3", person.name);
        addText(card, "p", `순위 ${{person.rank}}위 · 누적 ${{person.distance.toFixed(2)}} / ${{targetKm.toFixed(2)}} km`);
        addText(card, "p", remaining > 0
          ? `목표까지 ${{remaining.toFixed(2)}} km · 남은 기간 하루 평균 ${{(remaining / remainingDays).toFixed(2)}} km 필요`
          : "목표 거리를 달성했습니다.");
        results.appendChild(card);
      }});
      if (matches.length > 30) addText(results, "p", `검색 결과가 ${{matches.length}}명입니다. 이름을 더 입력해 범위를 좁혀 주세요.`, "muted");
    }});
  </script>
</body>
</html>
"""
    page_path = output_dir / "index.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path
