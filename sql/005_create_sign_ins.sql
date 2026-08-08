-- One row per actual sign-in.
--
-- users.last_seen_at answers "when was this person last here" but it is a single
-- column that gets overwritten, so it can never answer "how many times" or "how
-- many people were here on Tuesday". That needs an event, not a state.
--
-- The catch is that the auth dependency runs on EVERY authenticated request, so
-- writing a row there would log requests, not sign-ins - one story would look
-- like several. token_iat is the Google ID token's issued-at claim: it is fixed
-- for the life of a token and only changes when Google issues a new one, which
-- is exactly what a sign-in is. The UNIQUE constraint then does the counting -
-- the same token arriving fifty times inserts once and the rest are no-ops.
CREATE TABLE sign_ins (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    token_iat  BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, token_iat)
);

-- The admin page reads this as "the last N days", newest first.
CREATE INDEX sign_ins_created_at_idx ON sign_ins (created_at DESC);
