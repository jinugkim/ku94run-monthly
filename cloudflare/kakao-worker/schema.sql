CREATE TABLE IF NOT EXISTS members (
    member TEXT PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS invitations (
    token_hash TEXT PRIMARY KEY,
    member TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    reserved_at INTEGER,
    used_at INTEGER
);

CREATE TABLE IF NOT EXISTS oauth_states (
    state TEXT PRIMARY KEY,
    invite_hash TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS invitations_expiry ON invitations(expires_at);
CREATE INDEX IF NOT EXISTS oauth_states_expiry ON oauth_states(expires_at);
