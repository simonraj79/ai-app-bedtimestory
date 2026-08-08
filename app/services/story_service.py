import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

from app.database import get_conn
from app.schemas import Story
from app.services.gemini_service import GEMINI_MODEL


def save_story(child_name: str, theme: str, story: str, user_id: int) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO stories (child_name, theme, story, model_name, user_id) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (child_name, theme, story, GEMINI_MODEL, user_id),
                )
            conn.commit()
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
