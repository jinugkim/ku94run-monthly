# Run-teller Garmin Challenge Strategy Engine

가민 커스텀 챌린지 진행 상황을 불러와 목표 거리 달성량을 계산하고, Gemini로 Run-teller 코칭 리포트를 생성합니다. 워치 생체 데이터는 사용하지 않습니다.

## 실행

Python 3.12 이상에서 의존성을 설치하고 환경 변수를 설정한 뒤 `python main.py`를 실행합니다.

필수 환경 변수: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMIN_CHALLENGE_UUID`, `GEMINI_API_KEY`

선택 환경 변수: `TOKEN_STORE_PATH` (기본 `~/.garminconnect`), `SLACK_WEBHOOK_URL`, `GARMIN_CHALLENGE_TARGET_KM`, `GEMINI_MODEL` (기본 `gemini-3.8-flash`)

목표 거리는 기본적으로 챌린지명에서 `200km`처럼 추출합니다. 이름에 목표 거리가 없거나 추출값을 덮어쓰려면 `GARMIN_CHALLENGE_TARGET_KM`에 목표 거리(km)를 지정하세요.

GitHub Actions는 `.github/workflows/runteller_cron.yml`에서 매일 KST 07:00에 실행되도록 구성되어 있습니다. 저장소의 Actions secrets에 필수 Garmin 값과 선택 Slack 웹훅을 등록하세요. Garmin 토큰 캐시는 해당 저장소의 Actions 캐시에 저장되므로 저장소 접근 권한을 제한하세요.

Gemini가 코칭 리포트를 생성하고, `Courier` 모듈이 결과를 전송합니다. 현재 Slack 및 콘솔을 지원하며, 카카오톡이나 앱 연동은 같은 인터페이스를 구현하는 courier로 추가할 수 있습니다. GitHub Actions는 최신 코칭 리포트를 정적 GitHub Pages 사이트에 배포합니다.

GitHub Actions 사용 시 `GEMINI_API_KEY`를 저장소 Actions secret으로 등록하세요. Gemini API 키는 Google AI Studio에서 만들 수 있습니다. `GEMINI_MODEL`은 필요하면 Repository variable로 지정할 수 있습니다.

Pages를 처음 사용할 때 저장소의 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 설정하세요. Pages는 공개로 배포되며, 페이지에는 본인 목표 거리와 코칭 내용만 포함됩니다. 새 실행마다 같은 페이지 주소의 최신 리포트가 갱신됩니다.
