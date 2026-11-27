# [통합 완료 · Archived] ku94run-monthly → `jinugkim/ku94run`

> **이 저장소는 2026-11-27부로 [`jinugkim/ku94run`](https://github.com/jinugkim/ku94run) 단일 모노레포의 `pipelines/monthly/` 및 `web/`로 통합되어 읽기 전용(Archived)으로 전환되었습니다.**
>
> - **통합 저장소**: https://github.com/jinugkim/ku94run
> - **통합 서비스 URL**: https://ku94run-challenge.web.app/monthly/ (구 `jinugkim.github.io/ku94run-monthly/` 자동 리다이렉트 적용)

---

## 최종 이관 및 아키텍처 전환 요약

| 항목 | 기존 (`ku94run-monthly`) | 통합 후 (`jinugkim/ku94run`) |
| :--- | :--- | :--- |
| **웹 리포트 UI** | Python 정적 HTML 생성 (`report_page.py`, `archive_pages.py`) → GitHub Pages | Next.js 16 네이티브 UI (`/monthly/`, 크루 배너·SVG 추이 차트·연간 왕중왕 포디움·월별 아카이브·다크모드) → Firebase Hosting |
| **데이터 저장소** | Git `main` 일 19회 자동 커밋 (`data/standings.json`, `data/archives/`) | Cloud Firestore (`monthly_current/latest`, `monthly_archives/2026-01~10`, `monthly_yearly/2026`) |
| **수집 자동화** | Cloud Scheduler → GitHub Actions (`runteller_cron.yml`) | **Cloud Scheduler → Cloud Run Job (`ku94run-monthly-collect`, `run-teller`, `asia-northeast3`)** 직결 (GitHub Actions 미사용) |
| **Garmin 토큰 유지** | GitHub `actions/cache` (7일 만료) | Firestore `system_state/garmin_tokens` 영속 저장 (`garmin_token_store.py`) |
| **카카오톡 발송 / Cloudflare** | Cloudflare Worker/D1 + `kakao_coaching_message.yml` | **전면 폐기** (구 Cloud Scheduler `ku94run-1-collect`, `ku94run-2-send` 삭제 및 워크플로 비활성화 완료) |

### 보존된 과거 데이터
- 2026년 1~10월 확정 아카이브(10개월, 연간 누적 `44,446.9 km`) 및 11월 최신 스냅샷은 `ku94run-challenge` Cloud Firestore와 `jinugkim/ku94run/data/monthly/`에 모두 이관되었습니다.
