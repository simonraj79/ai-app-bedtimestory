import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

from app.database import get_conn
from app.schemas import MyChild, MyGenre, MyStats, MyStoryPoint, Story
from app.services.gemini_service import GEMINI_MODEL
from app.services.text_stats import analyse


def save_story(child_name: str, theme: str, story: str, user_id: int) -> None:
    # Measured here rather than by the caller, and written in the same INSERT:
    # there is one code path that stores a story, so every story gets its
    # statistics and no route can forget to ask for them.
    stats = analyse(story, theme)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO stories (child_name, theme, story, model_name, user_id, "
                    "                     word_count, sentence_count, reading_seconds, "
                    "                     reading_ease, grade_level, genre, genre_hits) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        child_name, theme, story, GEMINI_MODEL, user_id,
                        stats["word_count"], stats["sentence_count"],
                        stats["reading_seconds"], stats["reading_ease"],
                        stats["grade_level"], stats["genre"],
                        ",".join(stats["genre_hits"]),
                    ),
                )
            conn.commit()
    except psycopg.Error:
        raise HTTPException(
            status_code=502,
            detail="Postgres is not reachable. Check your database connection."
        )


def fetch_my_stats(user_id: int, is_admin: bool = False) -> MyStats:
    """One reader's own totals, across everything they have made - not just the last ten.

    Every query here is filtered by user_id from the verified token. There is no
    parameter that could widen it to somebody else's rows, which is the whole
    difference between this and the admin view.
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # COALESCE on the sums, not on the averages: nothing made yet is
                # honestly zero words, but an average of no stories is not zero -
                # it is nothing, and printing 0 would claim these stories are
                # unreadably simple rather than absent.
                cur.execute(
                    "SELECT count(*)                                  AS stories, "
                    "       COALESCE(sum(word_count), 0)::int         AS words, "
                    "       COALESCE(sum(reading_seconds), 0)::int    AS reading_seconds, "
                    "       round(avg(word_count))::int               AS avg_words, "
                    "       round(avg(grade_level)::numeric, 1)::float8 AS avg_grade, "
                    "       max(word_count)                           AS longest_words, "
                    "       to_char(min(created_at), 'YYYY-MM-DD')    AS first_story, "
                    "       to_char(max(created_at), 'YYYY-MM-DD')    AS last_story, "
                    "       count(*) FILTER (WHERE word_count IS NULL)::int AS unanalysed "
                    "FROM stories WHERE user_id = %s",
                    (user_id,),
                )
                totals = cur.fetchone()

                cur.execute(
                    "SELECT genre, count(*) AS stories FROM stories "
                    "WHERE user_id = %s AND genre IS NOT NULL "
                    "GROUP BY genre ORDER BY count(*) DESC, genre",
                    (user_id,),
                )
                genres = [MyGenre(**row) for row in cur.fetchall()]

                # Who the stories were for. The most personal number here, and
                # the one a parent is most likely to want.
                cur.execute(
                    "SELECT child_name, count(*) AS stories FROM stories "
                    "WHERE user_id = %s GROUP BY child_name "
                    "ORDER BY count(*) DESC, child_name",
                    (user_id,),
                )
                children = [MyChild(**row) for row in cur.fetchall()]

                # Oldest first so a chart reads left to right, but take the
                # newest 30 - a chart of two hundred columns on a phone is a
                # texture, not a reading.
                cur.execute(
                    "SELECT * FROM ( "
                    "  SELECT to_char(created_at, 'YYYY-MM-DD') AS created_at, "
                    "         child_name, theme, word_count, grade_level, genre, id "
                    "  FROM stories WHERE user_id = %s ORDER BY id DESC LIMIT 30 "
                    ") s ORDER BY s.id",
                    (user_id,),
                )
                series = [
                    MyStoryPoint(**{k: v for k, v in row.items() if k != "id"})
                    for row in cur.fetchall()
                ]

        return MyStats(
            **totals, genres=genres, children=children, series=series, is_admin=is_admin
        )
    except psycopg.Error:
        raise HTTPException(
            status_code=502,
            detail="Postgres is not reachable. Check your database connection."
        )


def fetch_recent_stories(user_id: int, limit: int = 10) -> list[Story]:
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, child_name, theme, story, model_name, "
                    "       word_count, sentence_count, reading_seconds, "
                    "       reading_ease, grade_level, genre, genre_hits, "
                    "       to_char(created_at, 'YYYY-MM-DD HH24:MI') AS created_at "
                    "FROM stories WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                    (user_id, limit),
                )
                return [Story(**row) for row in cur.fetchall()]
    except psycopg.Error:
        raise HTTPException(
            status_code=502,
            detail="Postgres is not reachable. Check your database connection."
        )
