"""Render and publish-ready package the latest coaching report as a static page."""

from datetime import datetime
from html import escape
import os
from pathlib import Path
from zoneinfo import ZoneInfo

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
    report_text = escape(report)
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
    article {{ padding: 22px; border: 1px solid #e0e5df; border-radius: 16px; background: white; }}
    pre {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.75; }}
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
    <article><pre>{report_text}</pre></article>
    <footer>생성 시각: {generated_at}. 거리 목표가 우선이며 페이스는 사용자가 직접 관리합니다.</footer>
  </main>
</body>
</html>
"""
    page_path = output_dir / "index.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path
