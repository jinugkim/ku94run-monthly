const TOKEN_URL = "https://kauth.kakao.com/oauth/token";
const AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize";
const encoder = new TextEncoder();

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function page(title, message, status = 200) {
  const escape = (value) => value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  return new Response(`<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${escape(title)}</title><body><main><h1>${escape(title)}</h1><p>${escape(message)}</p></main></body></html>`, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function randomToken(bytes = 32) {
  const data = crypto.getRandomValues(new Uint8Array(bytes));
  return [...data].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function authorized(request, token) {
  return Boolean(token) && request.headers.get("Authorization") === `Bearer ${token}`;
}

async function makeInvite(request, env) {
  if (!authorized(request, env.ADMIN_TOKEN)) return json({ error: "unauthorized" }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400); }
  const member = typeof body.member === "string" ? body.member.trim() : "";
  if (!member || member.length > 64 || /[\r\n]/.test(member)) return json({ error: "invalid_member" }, 400);

  const token = randomToken();
  const expiresAt = Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60;
  await env.TOKENS_DB.prepare(
    "INSERT INTO invitations (token_hash, member, expires_at) VALUES (?, ?, ?)",
  ).bind(await sha256(token), member, expiresAt).run();
  return json({ member, invite_url: `${env.PUBLIC_BASE_URL.replace(/\/$/, "")}/join/${token}`, expires_at: expiresAt }, 201);
}

async function startOAuth(request, env, token) {
  const inviteHash = await sha256(token);
  const now = Math.floor(Date.now() / 1000);
  const invite = await env.TOKENS_DB.prepare(
    "SELECT member FROM invitations WHERE token_hash = ? AND reserved_at IS NULL AND used_at IS NULL AND expires_at > ?",
  ).bind(inviteHash, now).first();
  if (!invite) return page("초대 링크를 사용할 수 없습니다", "링크가 만료됐거나 이미 사용되었습니다. 초대한 사람에게 새 링크를 요청하세요.", 410);
  const reservation = await env.TOKENS_DB.prepare(
    "UPDATE invitations SET reserved_at = ? WHERE token_hash = ? AND reserved_at IS NULL AND used_at IS NULL AND expires_at > ?",
  ).bind(now, inviteHash, now).run();
  if (!reservation.meta.changes) return page("초대 링크를 사용할 수 없습니다", "이미 사용 중이거나 만료된 링크입니다.", 410);

  const state = randomToken();
  const expiresAt = Math.floor(Date.now() / 1000) + 10 * 60;
  await env.TOKENS_DB.prepare(
    "INSERT INTO oauth_states (state, invite_hash, expires_at) VALUES (?, ?, ?)",
  ).bind(state, inviteHash, expiresAt).run();
  const authorize = new URL(AUTHORIZE_URL);
  authorize.search = new URLSearchParams({
    client_id: env.KAKAO_REST_API_KEY,
    redirect_uri: `${env.PUBLIC_BASE_URL.replace(/\/$/, "")}/oauth/callback`,
    response_type: "code",
    scope: "talk_message",
    state,
  });
  return Response.redirect(authorize.toString(), 302);
}

async function finishOAuth(request, env) {
  const url = new URL(request.url);
  const state = url.searchParams.get("state") || "";
  const code = url.searchParams.get("code");
  if (!state) return page("인증을 완료할 수 없습니다", "인증 상태 정보가 없습니다. 초대 링크를 다시 열어 주세요.", 400);

  const storedState = await env.TOKENS_DB.prepare(
    "SELECT invite_hash FROM oauth_states WHERE state = ? AND expires_at > ?",
  ).bind(state, Math.floor(Date.now() / 1000)).first();
  await env.TOKENS_DB.prepare("DELETE FROM oauth_states WHERE state = ?").bind(state).run();
  if (!storedState) return page("인증 링크가 만료되었습니다", "초대 링크를 다시 열어 주세요.", 400);
  if (!code) return page("카카오 동의가 완료되지 않았습니다", "메시지 권한 동의를 완료하려면 초대 링크를 다시 열어 주세요.", 400);

  const invite = await env.TOKENS_DB.prepare(
    "SELECT member FROM invitations WHERE token_hash = ? AND reserved_at IS NOT NULL AND used_at IS NULL AND expires_at > ?",
  ).bind(storedState.invite_hash, Math.floor(Date.now() / 1000)).first();
  if (!invite) return page("초대 링크를 사용할 수 없습니다", "링크가 만료됐거나 이미 사용되었습니다.", 410);

  const tokenResponse = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded;charset=utf-8" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: env.KAKAO_REST_API_KEY,
      redirect_uri: `${env.PUBLIC_BASE_URL.replace(/\/$/, "")}/oauth/callback`,
      code,
      client_secret: env.KAKAO_CLIENT_SECRET,
    }),
  });
  if (!tokenResponse.ok) {
    console.error("Kakao token exchange failed", tokenResponse.status);
    return page("카카오 인증을 마무리하지 못했습니다", "초대한 사람에게 새 링크를 요청해 주세요.", 502);
  }
  const tokens = await tokenResponse.json();
  if (!tokens.refresh_token) return page("갱신 토큰을 받지 못했습니다", "카카오 로그인 설정을 확인한 뒤 새 초대 링크를 요청해 주세요.", 502);

  const now = Math.floor(Date.now() / 1000);
  await env.TOKENS_DB.batch([
    env.TOKENS_DB.prepare(
      "INSERT INTO members (member, refresh_token, updated_at) VALUES (?, ?, ?) ON CONFLICT(member) DO UPDATE SET refresh_token = excluded.refresh_token, updated_at = excluded.updated_at",
    ).bind(invite.member, tokens.refresh_token, now),
    env.TOKENS_DB.prepare("UPDATE invitations SET used_at = ? WHERE token_hash = ?").bind(now, storedState.invite_hash),
  ]);
  return page("카카오 동의가 완료되었습니다", "이제 이 계정으로 러닝 코치 요약을 받을 수 있습니다. 이 창을 닫으셔도 됩니다.");
}

async function internalTokens(request, env) {
  if (!authorized(request, env.SYNC_TOKEN)) return json({ error: "unauthorized" }, 401);
  if (request.method === "GET") {
    const { results } = await env.TOKENS_DB.prepare("SELECT member, refresh_token FROM members ORDER BY member").all();
    return json(Object.fromEntries(results.map(({ member, refresh_token }) => [member, refresh_token])));
  }
  if (request.method === "PUT") {
    let body;
    try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400); }
    const member = typeof body.member === "string" ? body.member : "";
    const refreshToken = typeof body.refresh_token === "string" ? body.refresh_token : "";
    if (!member || !refreshToken) return json({ error: "member_and_refresh_token_required" }, 400);
    await env.TOKENS_DB.prepare(
      "INSERT INTO members (member, refresh_token, updated_at) VALUES (?, ?, ?) ON CONFLICT(member) DO UPDATE SET refresh_token = excluded.refresh_token, updated_at = excluded.updated_at",
    ).bind(member, refreshToken, Math.floor(Date.now() / 1000)).run();
    return json({ saved: true });
  }
  return json({ error: "method_not_allowed" }, 405);
}

async function importTokens(request, env) {
  if (!authorized(request, env.ADMIN_TOKEN)) return json({ error: "unauthorized" }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400); }
  if (!body || typeof body !== "object" || Array.isArray(body)) return json({ error: "expected_member_token_map" }, 400);
  const entries = Object.entries(body);
  if (entries.some(([member, token]) => !member || typeof token !== "string" || !token)) return json({ error: "invalid_member_token_map" }, 400);
  const now = Math.floor(Date.now() / 1000);
  const statements = entries.map(([member, token]) => env.TOKENS_DB.prepare(
    "INSERT INTO members (member, refresh_token, updated_at) VALUES (?, ?, ?) ON CONFLICT(member) DO UPDATE SET refresh_token = excluded.refresh_token, updated_at = excluded.updated_at",
  ).bind(member, token, now));
  if (statements.length) await env.TOKENS_DB.batch(statements);
  return json({ imported: entries.length });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/admin/invites") return makeInvite(request, env);
    if (request.method === "POST" && url.pathname === "/admin/import") return importTokens(request, env);
    if ((request.method === "GET" || request.method === "PUT") && url.pathname === "/internal/tokens") return internalTokens(request, env);
    if (request.method === "GET" && url.pathname.startsWith("/join/")) return startOAuth(request, env, url.pathname.slice("/join/".length));
    if (request.method === "GET" && url.pathname === "/oauth/callback") return finishOAuth(request, env);
    return json({ error: "not_found" }, 404);
  },
};
