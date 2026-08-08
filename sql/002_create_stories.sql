CREATE TABLE stories (
    id          SERIAL PRIMARY KEY,
    child_name  TEXT NOT NULL,
    theme       TEXT NOT NULL,
    story       TEXT NOT NULL,
    model_name  TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
