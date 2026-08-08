import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

from app.database import get_conn
from app.schemas import (
    UsageAction,
    UsageDay,
    UsageGenre,
    UsageResponse,
    UsageTotals,
    UsageUser,
)

# Rows written before sign-in existed have no owner. The feed names them rather
# than dropping them, so the totals and the list agree with each other.
UNATTRIBUTED = "(before sign-in)"


def fetch_usage() -> UsageResponse:
    """Who has signed in, how much each has used, and what happened lately."""
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT (SELECT count(*) FROM users)        AS users, "
                    "       (SELECT count(*) FROM sign_ins)     AS sign_ins, "
                    "       (SELECT count(*) FROM stories)      AS stories, "
                    "       (SELECT count(*) FROM interactions) AS questions"
                )
                totals = UsageTotals(**cur.fetchone())

                cur.execute(
                    "SELECT u.id, u.email, u.name, "
                    "       to_char(u.created_at, 'YYYY-MM-DD HH24:MI')   AS created_at, "
                    "       to_char(u.last_seen_at, 'YYYY-MM-DD HH24:MI') AS last_seen_at, "
                    "       (SELECT count(*) FROM sign_ins g WHERE g.user_id = u.id)     AS sign_ins, "
                    "       (SELECT count(*) FROM stories s WHERE s.user_id = u.id)      AS stories, "
                    "       (SELECT count(*) FROM interactions i WHERE i.user_id = u.id) AS questions "
                    "FROM users u ORDER BY u.last_seen_at DESC"
                )
                users = [UsageUser(**row) for row in cur.fetchall()]

                # generate_series, not GROUP BY: a day with no activity has no
                # rows to group, so grouping alone silently drops quiet days and
                # a 14-day chart would draw a misleadingly continuous line.
                cur.execute(
                    "WITH days AS ( "
                    "    SELECT generate_series("
                    "        current_date - interval '13 days', current_date, interval '1 day'"
                    "    )::date AS day "
                    ") "
                    "SELECT to_char(d.day, 'YYYY-MM-DD') AS day, "
                    "  (SELECT count(*) FROM sign_ins g "
                    "     WHERE g.created_at::date = d.day) AS sign_ins, "
                    "  (SELECT count(*) FROM stories s "
                    "     WHERE s.created_at::date = d.day) AS stories, "
                    "  (SELECT count(*) FROM interactions i "
                    "     WHERE i.created_at::date = d.day) AS questions, "
                    "  (SELECT count(DISTINCT x.user_id) FROM ( "
                    "       SELECT user_id, created_at FROM stories "
                    "       UNION ALL SELECT user_id, created_at FROM interactions "
                    "       UNION ALL SELECT user_id, created_at FROM sign_ins "
                    "   ) x WHERE x.created_at::date = d.day AND x.user_id IS NOT NULL"
                    "  ) AS people "
                    "FROM days d ORDER BY d.day"
                )
                daily = [UsageDay(**row) for row in cur.fetchall()]

                # Stories written before the stats columns existed have a NULL
                # genre, and "unanalysed" is not a genre - counting them would
                # invent a category and average their missing word counts as
                # nothing. Rounding happens in SQL so the numbers arrive ready
                # to print, and the tie-break on genre keeps the order stable
                # between calls rather than however Postgres happened to group.
                cur.execute(
                    "SELECT genre, "
                    "       count(*)                                    AS stories, "
                    "       round(avg(word_count))::int                 AS avg_words, "
                    "       round(avg(grade_level)::numeric, 1)::float8 AS avg_grade "
                    "FROM stories WHERE genre IS NOT NULL "
                    "GROUP BY genre ORDER BY count(*) DESC, genre"
                )
                genres = [UsageGenre(**row) for row in cur.fetchall()]

                # Both tables, one timeline. The ordering and the cut happen
                # inside the union so it is the real timestamps being compared,
                # not the display strings.
                cur.execute(
                    "SELECT kind, email, detail, "
                    "       to_char(happened_at, 'YYYY-MM-DD HH24:MI') AS created_at "
                    "FROM ( "
                    "    SELECT 'story' AS kind, COALESCE(u.email, %s) AS email, "
                    "           s.child_name || ' — ' || s.theme AS detail, "
                    "           s.created_at AS happened_at "
                    "    FROM stories s LEFT JOIN users u ON u.id = s.user_id "
                    "    UNION ALL "
                    "    SELECT 'question', COALESCE(u.email, %s), "
                    "           left(i.question, 80), i.created_at "
                    "    FROM interactions i LEFT JOIN users u ON u.id = i.user_id "
                    "    ORDER BY happened_at DESC LIMIT 20 "
                    ") AS actions ORDER BY happened_at DESC",
                    (UNATTRIBUTED, UNATTRIBUTED),
                )
                recent = [UsageAction(**row) for row in cur.fetchall()]

        return UsageResponse(
            totals=totals, users=users, daily=daily, genres=genres, recent=recent
        )
    except psycopg.Error:
        raise HTTPException(
            status_code=502,
            detail="Postgres is not reachable. Check your database connection."
        )
