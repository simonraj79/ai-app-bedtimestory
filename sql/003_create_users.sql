-- One row per person who has signed in with Google.
--
-- The key is google_sub, not email: Google's `sub` claim is stable for the
-- lifetime of the account, while an email address can be changed by its owner.
-- Keyed on email, a rename would fork one person into two rows and split their
-- stories and questions between them.
CREATE TABLE users (
    id           SERIAL PRIMARY KEY,
    google_sub   TEXT NOT NULL UNIQUE,
    email        TEXT NOT NULL,
    name         TEXT NOT NULL,
    picture      TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
);
