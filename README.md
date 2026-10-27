# KU94RUN Monthly Garmin Challenge Strategy Engine

가민 커스텀 챌린지 진행 상황을 불러와 목표 거리 달성량을 계산하고, Gemini로 Run-teller 코칭 리포트를 생성합니다. 워치 생체 데이터는 사용하지 않습니다.

## 실행

Python 3.12 이상에서 의존성을 설치하고 환경 변수를 설정한 뒤 `python main.py`를 실행합니다.

필수 환경 변수: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GEMINI_API_KEY`. 로컬 실행에서 연도별 YAML이 없을 때는 `GARMIN_CHALLENGE_UUID`도 필요합니다. GitHub Actions는 `data/challenges/<연도>.yaml`의 활성 항목을 읽고 해당 `garmin_uuid_secret`에 해당하는 secret으로 Garmin 챌린지를 조회합니다.

선택 환경 변수: `TOKEN_STORE_PATH` (기본 `~/.garminconnect`), `SLACK_WEBHOOK_URL`, `GARMIN_CHALLENGE_TARGET_KM`, `GEMINI_MODEL` (기본 `gemini-3.8-flash`)

참가자 그룹을 구분할 수 없으므로 거리 달성 인원과 개인 코칭은 모든 그룹에 공통으로 적용되는 거리 기준을 씁니다. YAML 최상위 `target_distance_km`를 우선 사용하고, 없으면 그룹별 목표 중 가장 큰 거리를 씁니다. YAML에 목표가 없으면 `GARMIN_CHALLENGE_TARGET_KM`, 그다음 챌린지명에서 목표를 찾습니다.

GitHub Actions는 `.github/workflows/runteller_cron.yml`에서 매일 KST 02:10에 리포트 페이지를 갱신하고, `.github/workflows/kakao_coaching_message.yml`에서 KST 04:10에 카카오 코칭 메시지를 발송합니다. 두 워크플로는 UTC 기준으로 각각 17:10, 19:10에 예약되어 있습니다. GitHub Actions 스케줄은 시스템 부하에 따라 지연될 수 있습니다. 저장소의 Actions secrets에 필수 Garmin 값과 선택 Slack 웹훅을 등록하세요. Garmin 토큰 캐시는 해당 저장소의 Actions 캐시에 저장되므로 저장소 접근 권한을 제한하세요.

Gemini가 코칭 리포트를 생성하고, `Courier` 모듈이 결과를 전송합니다. 현재 Slack 및 콘솔을 지원하며, 카카오톡이나 앱 연동은 같은 인터페이스를 구현하는 courier로 추가할 수 있습니다. GitHub Actions는 최신 코칭 리포트와 오늘의 러닝 보드를 GitHub Pages에 배포하고, 날짜별 참가자 거리·순위 스냅샷을 `data/standings.json`에 저장합니다. 스냅샷은 180일간 유지됩니다.

GitHub Actions 사용 시 `GEMINI_API_KEY`를 저장소 Actions secret으로 등록하세요. Gemini API 키는 Google AI Studio에서 만들 수 있습니다. `GEMINI_MODEL`은 필요하면 Repository variable로 지정할 수 있습니다.

### 카카오톡으로 리포트 공유

리포트 하단의 **코치 요약 공유하기** 버튼은 카카오 JavaScript SDK v2로 챌린지명, 누적 거리, 남은 목표 거리·기간, 오늘 코칭의 앞부분을 200자 이내로 요약해 공유합니다. GitHub Actions secret `KAKAO_JS_KEY`에 카카오 디벨로퍼스의 **JavaScript 키**를 등록하세요. 워크플로가 페이지를 만들 때 키를 전달합니다. 브라우저 SDK가 사용하는 키이므로 배포된 `site/index.html`에서는 공개됩니다. REST API 키는 사용하지 마세요.

카카오 디벨로퍼스의 **JavaScript SDK 도메인**에 `https://jinugkim.github.io`를, **제품 링크 관리**의 웹 도메인에 `https://jinugkim.github.io`를 등록해야 합니다. 버튼을 누르면 카카오톡 공유 대상 선택 화면이 열리고 사용자가 친구나 채팅방을 선택합니다.

정적 호스팅에서 SDK v2 로그인은 리다이렉트 후 인가 코드를 서버에서 토큰으로 교환해야 합니다. 따라서 서버 없이 로그인한 사용자의 나와의 채팅방에 직접 보내는 메시지 API를 구현할 수 없습니다. 현재 페이지는 로그인 없이 쓸 수 있는 SDK v2 카카오톡 공유를 사용합니다. 카카오 안내: [JavaScript SDK 로그인](https://developers.kakao.com/docs/ko/kakaologin/js), [JavaScript SDK 카카오톡 공유](https://developers.kakao.com/docs/ko/kakaotalk-share/js-link).

### GitHub Actions에서 팀원별 나에게 메시지 자동 발송

매일 02:10에 생성한 리포트에서 요약 메시지 자료를 공개 Pages에 함께 배포하고, 04:10에 별도 GitHub Actions 워크플로가 이를 읽어 Cloudflare D1에 보관된 각 사용자의 갱신 토큰으로 본인의 카카오톡 나와의 채팅방에 보냅니다. 팀원은 초대 링크를 열고 카카오 로그인 및 `talk_message` 동의만 하면 됩니다. 로컬 Python 실행이나 토큰 파일 전달은 필요하지 않습니다. 한 사람의 토큰으로 다른 팀원의 채팅방에 보낼 수는 없습니다.

#### 운영 체크리스트

- 저장소 Actions secrets: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, 연도·월별 `GARMIN_CHALLENGE_<YYYY>_<MM>_UUID`, `GEMINI_API_KEY`, `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `KAKAO_SYNC_TOKEN`, `KAKAO_JS_KEY`
- 저장소 Actions variable: `KAKAO_SYNC_URL` (Cloudflare Worker의 `workers.dev` 주소)
- Cloudflare Worker secrets: `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `ADMIN_TOKEN`, `SYNC_TOKEN`. `SYNC_TOKEN`은 GitHub의 `KAKAO_SYNC_TOKEN`과 같은 값이어야 합니다.
- 토큰 원본은 Cloudflare D1입니다. `KAKAO_REFRESH_TOKENS_JSON` secret은 이전 로컬/환경변수 방식의 잔여 항목으로, 현재 Actions 발송 워크플로에서는 사용하지 않습니다.
- 공개 보드를 끄려면 GitHub Actions repository variable `PUBLIC_BOARD_ENABLED`를 소문자 `false`로 설정합니다. 이후 페이지에서 보드를 숨기고 새 참가자 기록 저장을 중단합니다. 기존 `data/standings.json` 및 Git 이력은 자동 삭제되지 않으므로 과거 데이터 공개도 중단해야 한다면 별도 정리가 필요합니다.
- 카카오 발송 이력은 Cloudflare D1의 `kakao_deliveries`에 날짜·팀원·상태별로 저장됩니다. 스키마를 갱신한 뒤 Worker를 배포해야 합니다.

  ```sh
  cd cloudflare/kakao-worker
  npx wrangler d1 execute run-teller-kakao --remote --file=schema.sql
  npx wrangler deploy
  ```

최근 수동 발송 확인: GitHub Actions run `40069548791`이 성공했습니다. 이는 워크플로가 오류 없이 끝났다는 뜻입니다. 이후 팀원별 결과는 `Report Kakao delivery history` 단계 및 D1 이력에서 확인하고, 실제 수신 여부는 수신자에게 확인하세요.

정기 운영은 별도 조치 없이 예약 실행을 사용합니다. 수동 점검은 먼저 **Run-teller Daily Challenge Strategy Cron**을 실행해 오늘 리포트를 Pages에 배포한 뒤, **Run-teller Kakao Coaching Message**를 실행합니다. 발송은 저장된 모든 팀원을 대상으로 하므로, 시험 실행도 전체 대상에게 메시지를 보냅니다. 최근 실행 확인 명령은 다음과 같습니다.

```sh
gh run list --repo jinugkim/ku94run-monthly \
  --workflow "Run-teller Kakao Coaching Message" --limit 5
gh run watch <실행_ID> --repo jinugkim/ku94run-monthly
gh run view <실행_ID> --repo jinugkim/ku94run-monthly --log
curl --fail --silent --show-error \
  -H "Authorization: Bearer $KAKAO_SYNC_TOKEN" \
  "$KAKAO_SYNC_URL/internal/deliveries?date=YYYY-MM-DD" | jq .
```

같은 날짜에 다시 실행하면 `sent` 수신자는 건너뛰고 명확한 실패(`failed`)만 재시도합니다. 네트워크 타임아웃처럼 카카오 응답을 받지 못해 전송 여부가 불명확하면 `uncertain`으로 저장하고 자동 재시도하지 않습니다. 전송 성공 뒤 D1에 성공 상태를 쓰기 전에 실행이 중단되면 `sending`으로 남으며, 중복 방지를 위해 자동 재시도하지 않습니다. 이 경우 Actions 로그와 D1 이력을 보고 수신 여부를 확인하세요. 카카오 전송과 D1 기록은 원자적 작업이 아니므로 이 경계 상황에는 수동 확인이 필요합니다. 발송 오류나 토큰 동기화 오류가 있으면 Actions 실행도 실패로 끝납니다. 토큰 만료·동의 철회라면 새 초대 링크를 발급해 다시 동의받으세요. 이 이력 기능을 처음 배포할 때 과거 발송은 자동 등록되지 않으므로, 같은 KST 날짜에 이미 발송했다면 그 날짜에는 재실행하지 말고 다음 날짜부터 자동 중복 방지를 사용하세요.

OAuth 동의 도중 닫거나 실패한 초대는 10분 뒤 다시 열 수 있습니다. 초대 링크는 7일간 유효하며 한 번 동의가 완료되면 다시 사용할 수 없습니다. 새 초대를 만들 때 만료된 초대와 OAuth 상태 기록을 정리합니다.

카카오 발송은 해당 날짜의 리포트 자료가 없으면 이전 날짜 메시지를 보내지 않고 실패 처리합니다. 이 경우 먼저 Daily 워크플로의 성공 여부와 Pages 배포를 확인한 후 Kakao 워크플로를 다시 실행하세요.

코드를 수정해 Worker 동작을 바꾼 경우에는 저장소에 반영한 뒤 Worker 디렉터리에서 `npx wrangler deploy`도 실행해야 변경 사항이 실제 서비스에 적용됩니다. Python 발송 코드와 워크플로 변경은 GitHub 저장소의 `main`에 반영되어야 다음 Actions 실행에 사용됩니다.

#### Cloudflare Worker 최초 설정

1. Node.js가 설치된 컴퓨터에서 저장소를 받고 Worker 디렉터리로 이동합니다.

   ```sh
   cd cloudflare/kakao-worker
   npx wrangler login
   npx wrangler d1 create run-teller-kakao
   ```

2. `d1 create` 출력의 ID를 `wrangler.toml`의 `database_id`에 넣습니다. Cloudflare 대시보드에서 `workers.dev` 주소를 확인하고 `PUBLIC_BASE_URL`을 그 주소로 바꾼 뒤 배포합니다.

   ```sh
   npx wrangler deploy
   npx wrangler d1 execute run-teller-kakao --remote --file=schema.sql
   ```

   예를 들어 Worker 주소가 `https://run-teller-kakao-auth.example.workers.dev`라면 카카오 디벨로퍼스 REST API 키의 로그인 리다이렉트 URI에 `https://run-teller-kakao-auth.example.workers.dev/oauth/callback`을 등록합니다. `talk_message` 동의 항목도 사용 설정합니다. `PUBLIC_BASE_URL`을 바꾼 뒤 Worker를 다시 배포하세요.

3. REST API 키와 **카카오 로그인 클라이언트 시크릿**을 Worker secret으로 등록합니다.

   ```sh
   npx wrangler secret put KAKAO_REST_API_KEY
   npx wrangler secret put KAKAO_CLIENT_SECRET
   ```

   초대 관리용 `ADMIN_TOKEN`도 생성해 Worker secret으로 등록합니다. 아래에서 발급된 초대 링크를 만들거나 기존 토큰을 가져올 때 사용합니다.

   ```sh
   export PUBLIC_BASE_URL="https://<worker-name>.<account-subdomain>.workers.dev"
   export ADMIN_TOKEN="$(openssl rand -hex 32)"
   printf '%s' "$ADMIN_TOKEN" | npx wrangler secret put ADMIN_TOKEN
   ```

4. Actions와 Worker 사이 인증 토큰을 만듭니다. 같은 값을 Wrangler와 GitHub Actions secret에 등록하고 Worker 주소는 Actions variable로 등록합니다.

   ```sh
   export KAKAO_SYNC_TOKEN="$(openssl rand -hex 32)"
   printf '%s' "$KAKAO_SYNC_TOKEN" | npx wrangler secret put SYNC_TOKEN
   printf '%s' "$KAKAO_SYNC_TOKEN" | gh secret set KAKAO_SYNC_TOKEN --repo jinugkim/ku94run-monthly
   gh variable set KAKAO_SYNC_URL --body "$PUBLIC_BASE_URL" --repo jinugkim/ku94run-monthly
   ```

   `PUBLIC_BASE_URL`은 앞 단계에서 설정한 Worker 주소로 지정합니다. 저장소 Actions secrets에는 기존 `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`도 필요합니다. Actions가 메시지 발송 시 토큰을 갱신하는 데 사용합니다.

#### 기존 토큰 가져오기 및 팀원 초대

현재 `kakao_refresh_tokens.json`이 있다면 Cloudflare에 한 번 가져옵니다. `ADMIN_TOKEN`과 `PUBLIC_BASE_URL`이 현재 터미널 환경에 설정되어 있어야 합니다.

```sh
curl --fail --silent --show-error -X POST "$PUBLIC_BASE_URL/admin/import" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @../../kakao_refresh_tokens.json
```

팀원별 초대 링크는 아래 요청으로 만듭니다. 응답으로 받은 `invite_url`을 해당 팀원에게 개인적으로 전달하세요. 링크는 7일간 유효하고 한 번만 사용할 수 있습니다.

```sh
curl --fail --silent --show-error -X POST "$PUBLIC_BASE_URL/admin/invites" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"member":"팀원식별자"}'
```

팀원이 링크에서 로그인과 동의를 마치면 토큰이 Cloudflare에 저장됩니다. 다음 Actions 실행에서 각자 본인의 나와의 채팅방으로 메시지가 발송됩니다. Actions 탭에서 **Run-teller Daily Challenge Strategy Cron**을 수동 실행해 확인할 수 있습니다. 기존 로컬 방식이 더 편하면 `python3 kakao_oauth_setup.py`도 계속 사용할 수 있으며, 생성한 JSON은 위 `/admin/import` 요청으로 가져오면 됩니다.

Pages를 처음 사용할 때 저장소의 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 설정하세요. Actions 설정에서 워크플로의 저장소 쓰기를 막고 있다면 **Settings → Actions → General → Workflow permissions**에서 쓰기를 허용해야 날짜별 기록을 저장할 수 있습니다. Pages와 공개 저장소의 날짜별 기록은 누구나 볼 수 있으므로 참가자 이름·거리·순위도 공개됩니다. 참가자 동의를 받고 공개 범위를 확인하세요. 공개가 적절하지 않다면 이름을 익명화하거나 보드 및 기록 저장을 비활성화해야 합니다. 보드는 누적 거리, 목표 달성 인원, 직전 기록 대비 거리 증가, 상위 순위표를 보여줍니다. 순위 그래프는 상위 6명과 본인의 최근 14회 기록을 표시하며, 첫 기록 다음부터 추이를 볼 수 있습니다.
