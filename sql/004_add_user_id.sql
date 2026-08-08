-- Attribute every row to the person who asked for it.
--
-- user_id is NULLABLE on purpose: rows written before sign-in existed have no
-- owner and never will. A NOT NULL column would need a fabricated owner for
-- them, which would be a lie in the data; NULL says "predates sign-in".
ALTER TABLE interactions ADD COLUMN user_id INTEGER REFERENCES users(id);
ALTER TABLE stories      ADD COLUMN user_id INTEGER REFERENCES users(id);

-- Every read is now "this user's newest N", so the index carries the sort too
-- and Postgres never has to sort the whole table to answer it.
CREATE INDEX interactions_user_id_id_idx ON interactions (user_id, id DESC);
CREATE INDEX stories_user_id_id_idx      ON stories (user_id, id DESC);
