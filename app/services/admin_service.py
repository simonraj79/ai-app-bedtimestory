import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

from app.database import get_conn
from app.schemas import UsageAction, UsageResponse, UsageTotals, UsageUser

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
                    "       (SELECT count(*) FROM stories)      AS stories, "
                    "       (SELECT count(*) FROM interactions) AS questions"
                )
                totals = UsageTotals(**cur.fetchone())

                cur.execute(
                    "SELECT u.id, u.email, u.name, "
                    "       to_char(u.created_at, 'YYYY-MM-DD HH24:MI')   AS created_at, "
                    "       to_char(u.last_seen_at, 'YYYY-MM-DD HH24:MI') AS last_seen_at, "
                    "       (SELECT count(*) FROM stories s WHERE s.user_id = u.id)      AS stories, "
                    "       (SELECT count(*) FROM interactions i WHERE i.user_id = u.id) AS questions "
                    "FROM users u ORDER BY u.last_seen_at DESC"
                )
                users = [UsageUser(**row) for row in cur.fetchall()]

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

        return UsageResponse(totals=totals, users=users, recent=recent)
    except psycopg.Error:
        raise HTTPException(
            status_code=502,
            detail="Postgres is not reachable. Check your database connection."
        )
