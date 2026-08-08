-- Measure each story as it is written: length, read-aloud time, how hard it is
-- to read, and what it is about.
--
-- Every column is NULLABLE on purpose: the stories already in the table were
-- written before any of this existed and have no statistics until they are
-- backfilled. NULL says "not analysed". NOT NULL would need a default, and a
-- zero-word story is a lie in the data - it would drag every average down while
-- looking exactly like a real measurement.
ALTER TABLE stories
    ADD COLUMN word_count      INTEGER,
    ADD COLUMN sentence_count  INTEGER,
    ADD COLUMN reading_seconds INTEGER,
    ADD COLUMN reading_ease    REAL,
    ADD COLUMN grade_level     REAL,
    ADD COLUMN genre           TEXT,
    -- The few words that chose the genre, comma-joined into TEXT rather than a
    -- TEXT[]. It is only ever read back whole, to show the reader why the label
    -- was picked; nothing queries inside it. An array would buy containment
    -- operators nobody uses and cost psycopg a list where every other column
    -- maps to a plain string. Do not "improve" this into TEXT[].
    ADD COLUMN genre_hits      TEXT;

-- The usage page groups stories by genre, so give that grouping an index rather
-- than a full scan as the table grows.
CREATE INDEX stories_genre_idx ON stories (genre);
