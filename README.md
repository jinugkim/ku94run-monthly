# Run-teller Garmin Challenge Strategy Engine

가민 커스텀 챌린지 진행 상황을 불러와 순위와 거리 격차를 계산하고, Run-teller 코칭 프롬프트를 생성합니다. 워치 생체 데이터는 사용하지 않습니다.

## 실행

Python 3.12 이상에서 의존성을 설치하고 환경 변수를 설정한 뒤 `python main.py`를 실행합니다.

필수 환경 변수: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMIN_CHALLENGE_UUID`

선택 환경 변수: `TOKEN_STORE_PATH` (기본 `~/.garminconnect`), `SLACK_WEBHOOK_URL`, `GARMIN_CHALLENGE_TARGET_KM`

목표 거리는 기본적으로 챌린지명에서 `200km`처럼 추출합니다. 이름에 목표 거리가 없거나 추출값을 덮어쓰려면 `GARMIN_CHALLENGE_TARGET_KM`에 목표 거리(km)를 지정하세요.

GitHub Actions는 `.github/workflows/runteller_cron.yml`에서 매일 KST 07:00에 실행되도록 구성되어 있습니다. 저장소의 Actions secrets에 필수 Garmin 값과 선택 Slack 웹훅을 등록하세요. Garmin 토큰 캐시는 해당 저장소의 Actions 캐시에 저장되므로 저장소 접근 권한을 제한하세요.

알림 전송은 `Notifier` 인터페이스 경계로 분리했습니다. 현재 Slack 및 콘솔 출력을 지원하며, 카카오톡은 추후 별도 notifier를 추가할 수 있습니다.
