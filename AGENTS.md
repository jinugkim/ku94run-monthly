# [Archived] ku94run-monthly AI Context

> **2026-11-27 통합 완료**: 이 프로젝트는 [`jinugkim/ku94run`](https://github.com/jinugkim/ku94run)으로 통합되었습니다.
> - 웹 UI: `https://ku94run-challenge.web.app/monthly/` (Firebase Hosting)
> - 월간 수집: `run-teller` 프로젝트 Cloud Run Job (`ku94run-monthly-collect`, `asia-northeast3`) + Cloud Scheduler (`50 6-23 * * *`, `5 0 * * *`, KST)
> - 데이터 저장소: `ku94run-challenge` Cloud Firestore (`monthly_current`, `monthly_archives`, `monthly_yearly`, `system_state/garmin_tokens`)
> - 카카오톡 발송 및 Cloudflare Worker/D1: 전면 폐기, 구 스케줄러(`ku94run-1-collect`, `ku94run-2-send`) 삭제 완료.
