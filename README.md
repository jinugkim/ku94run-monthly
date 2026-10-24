# Run-teller Garmin Challenge Strategy Engine

가민 커스텀 챌린지 진행 상황을 불러와 목표 거리 달성량을 계산하고, Gemini로 Run-teller 코칭 리포트를 생성합니다. 워치 생체 데이터는 사용하지 않습니다.

## 실행

Python 3.12 이상에서 의존성을 설치하고 환경 변수를 설정한 뒤 `python main.py`를 실행합니다.

필수 환경 변수: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMIN_CHALLENGE_UUID`, `GEMINI_API_KEY`

선택 환경 변수: `TOKEN_STORE_PATH` (기본 `~/.garminconnect`), `SLACK_WEBHOOK_URL`, `GARMIN_CHALLENGE_TARGET_KM`, `GEMINI_MODEL` (기본 `gemini-3.8-flash`)

목표 거리는 기본적으로 챌린지명에서 `200km`처럼 추출합니다. 이름에 목표 거리가 없거나 추출값을 덮어쓰려면 `GARMIN_CHALLENGE_TARGET_KM`에 목표 거리(km)를 지정하세요.

GitHub Actions는 `.github/workflows/runteller_cron.yml`에서 매일 KST 07:00에 실행되도록 구성되어 있습니다. 저장소의 Actions secrets에 필수 Garmin 값과 선택 Slack 웹훅을 등록하세요. Garmin 토큰 캐시는 해당 저장소의 Actions 캐시에 저장되므로 저장소 접근 권한을 제한하세요.

Gemini가 코칭 리포트를 생성하고, `Courier` 모듈이 결과를 전송합니다. 현재 Slack 및 콘솔을 지원하며, 카카오톡이나 앱 연동은 같은 인터페이스를 구현하는 courier로 추가할 수 있습니다. GitHub Actions는 최신 코칭 리포트와 오늘의 러닝 보드를 GitHub Pages에 배포하고, 날짜별 참가자 거리·순위 스냅샷을 `data/standings.json`에 저장합니다. 스냅샷은 180일간 유지됩니다.

GitHub Actions 사용 시 `GEMINI_API_KEY`를 저장소 Actions secret으로 등록하세요. Gemini API 키는 Google AI Studio에서 만들 수 있습니다. `GEMINI_MODEL`은 필요하면 Repository variable로 지정할 수 있습니다.

### 카카오톡으로 리포트 공유

리포트 하단의 **코치 요약 공유하기** 버튼은 카카오 JavaScript SDK v2로 챌린지명, 누적 거리, 남은 목표 거리·기간, 오늘 코칭의 앞부분을 200자 이내로 요약해 공유합니다. GitHub Actions secret `KAKAO_JS_KEY`에 카카오 디벨로퍼스의 **JavaScript 키**를 등록하세요. 워크플로가 페이지를 만들 때 키를 전달합니다. 브라우저 SDK가 사용하는 키이므로 배포된 `site/index.html`에서는 공개됩니다. REST API 키는 사용하지 마세요.

카카오 디벨로퍼스의 **JavaScript SDK 도메인**에 `https://jinugkim.github.io`를, **제품 링크 관리**의 웹 도메인에 `https://jinugkim.github.io`를 등록해야 합니다. 버튼을 누르면 카카오톡 공유 대상 선택 화면이 열리고 사용자가 친구나 채팅방을 선택합니다.

정적 호스팅에서 SDK v2 로그인은 리다이렉트 후 인가 코드를 서버에서 토큰으로 교환해야 합니다. 따라서 서버 없이 로그인한 사용자의 나와의 채팅방에 직접 보내는 메시지 API를 구현할 수 없습니다. 현재 페이지는 로그인 없이 쓸 수 있는 SDK v2 카카오톡 공유를 사용합니다. 카카오 안내: [JavaScript SDK 로그인](https://developers.kakao.com/docs/ko/kakaologin/js), [JavaScript SDK 카카오톡 공유](https://developers.kakao.com/docs/ko/kakaotalk-share/js-link).

### GitHub Actions에서 팀원별 나에게 메시지 자동 발송

GitHub Actions는 매일 리포트를 만든 뒤, `KAKAO_REFRESH_TOKENS_JSON`에 등록된 각 사용자의 토큰으로 본인의 나와의 채팅방에 러닝 코치 요약을 보냅니다. 각 팀원은 카카오 로그인을 통해 `talk_message` 권한에 동의해야 합니다. 한 사람의 토큰으로 다른 팀원의 나와의 채팅방에 보낼 수는 없습니다.

1. 카카오 디벨로퍼스에서 카카오 로그인을 켜고 `talk_message` 동의 항목을 설정합니다. REST API 키의 로그인 리다이렉트 URI에 아래 주소를 정확히 등록합니다.

   `http://localhost:8765/oauth/callback`

2. 서비스 관리자가 신뢰할 수 있는 로컬 환경에서 `python kakao_oauth_setup.py`를 실행하고, 안내에 따라 재발급한 REST API 키와 카카오 로그인 클라이언트 시크릿을 입력합니다. 브라우저에서 각 팀원이 자기 카카오 계정으로 로그인하고 동의해야 합니다. 스크립트가 받은 갱신 토큰을 로컬 `kakao_refresh_tokens.json`에 저장합니다. 팀원별로 한 번씩 진행하세요.

   이 파일은 `.gitignore`에 포함되어 있으므로 저장소에 커밋하지 마세요.

3. `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `KAKAO_REFRESH_TOKENS_JSON`을 저장소 Actions secrets로 등록합니다. 로컬 파일은 GitHub CLI로 직접 올릴 수 있습니다.

   `gh secret set KAKAO_REFRESH_TOKENS_JSON --repo jinugkim/run-teller < kakao_refresh_tokens.json`

4. `run-teller-kakao-token-rotator` GitHub App이 `run-teller` 저장소에 설치되어 있고, `GH_APP_ID`, `GH_APP_PRIVATE_KEY` secrets가 등록돼 있어야 합니다. 워크플로가 앱 토큰을 만들어 Kakao 갱신 토큰이 교체되면 GitHub secret도 자동 갱신합니다.

5. Actions 탭에서 **Run-teller Daily Challenge Strategy Cron**을 수동 실행해 확인합니다. 성공하면 각 동의 사용자 본인의 카카오톡 나와의 채팅방으로 요약이 도착합니다.

Pages를 처음 사용할 때 저장소의 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 설정하세요. Actions 설정에서 워크플로의 저장소 쓰기를 막고 있다면 **Settings → Actions → General → Workflow permissions**에서 쓰기를 허용해야 날짜별 기록을 저장할 수 있습니다. Pages와 공개 저장소의 날짜별 기록은 누구나 볼 수 있으므로 참가자 이름·거리·순위도 공개됩니다. 보드는 누적 거리, 목표 달성 인원, 직전 기록 대비 거리 증가, 상위 순위표를 보여줍니다. 순위 그래프는 상위 6명과 본인의 최근 14회 기록을 표시하며, 첫 기록 다음부터 추이를 볼 수 있습니다.
