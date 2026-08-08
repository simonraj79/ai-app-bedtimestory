from dotenv import load_dotenv

load_dotenv()  # Must run BEFORE importing modules that read os.environ at load time.

import os

import httpx
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_conn
from app.schemas import (
    AskRequest, AskResponse, CurrentUser, Interaction,
    Story, StoryRequest, StoryResponse, UsageResponse,
)
from app.services.gemini_service import (
    GEMINI_API_KEY, GEMINI_BASE_URL, call_gemini, generate_story,
)
from app.services.admin_service import fetch_usage
from app.services.auth_service import admin_user, current_user
from app.services.chat_service import save_interaction, fetch_recent_history
from app.services.story_service import save_story, fetch_recent_stories

# The frontend is deployed separately (Vercel), so the browser calls this API
# cross-origin. Only these origins may do so.
FRONTEND_ORIGINS = os.environ["FRONTEND_ORIGINS"].split(",")

app = FastAPI(title="AI Apps API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    # Authorization carries the Google ID token. Leave it out and the browser's
    # preflight is refused before the real request is ever sent - a failure that
    # shows up as "Failed to fetch" with nothing in the backend logs.
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/")
def root():
    return {"api": "AI Apps", "apps": ["chat", "bedtime"], "health": "/healthz"}


# --- App 1: Chat -------------------------------------------------------------

@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, user: CurrentUser = Depends(current_user)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    answer = call_gemini(question)
    save_interaction(question, answer, user.id)
    return AskResponse(answer=answer, history=fetch_recent_history(user.id))


@app.get("/history", response_model=list[Interaction])
def history(user: CurrentUser = Depends(current_user)):
    return fetch_recent_history(user.id)


# --- App 2: Bedtime Story ----------------------------------------------------

@app.post("/story", response_model=StoryResponse)
def story(payload: StoryRequest, user: CurrentUser = Depends(current_user)):
    child_name = payload.child_name.strip()
    theme = payload.theme.strip()
    if not child_name:
        raise HTTPException(status_code=400, detail="Please enter the child's name.")
    if not theme:
        raise HTTPException(status_code=400, detail="Please say what the story is about.")
    text = generate_story(child_name, theme, payload.length)
    save_story(child_name, theme, text, user.id)
    return StoryResponse(story=text, history=fetch_recent_stories(user.id))


@app.get("/stories", response_model=list[Story])
def stories(user: CurrentUser = Depends(current_user)):
    return fetch_recent_stories(user.id)


# --- Admin -------------------------------------------------------------------

# The dependency is a gate, not an argument - the route needs the check to run
# but has no use for the user it returns.
@app.get(
    "/admin/usage",
    response_model=UsageResponse,
    dependencies=[Depends(admin_user)],
)
def admin_usage():
    return fetch_usage()


# --- Shared ------------------------------------------------------------------

@app.get("/healthz")
def healthz():
    status = {"gemini": False, "postgres": False}
    try:
        with httpx.Client(timeout=10.0) as client:
            client.get(
                f"{GEMINI_BASE_URL}/models",
                headers={"x-goog-api-key": GEMINI_API_KEY},
            ).raise_for_status()
        status["gemini"] = True
    except httpx.HTTPError:
        pass
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        status["postgres"] = True
    except psycopg.Error:
        pass
    return status
