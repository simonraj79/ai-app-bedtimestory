from dotenv import load_dotenv

load_dotenv()  # Must run BEFORE importing modules that read os.environ at load time.

import os

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_conn
from app.schemas import (
    AskRequest, AskResponse, Interaction,
    Story, StoryRequest, StoryResponse,
)
from app.services.gemini_service import (
    GEMINI_API_KEY, GEMINI_BASE_URL, call_gemini, generate_story,
)
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
    allow_headers=["Content-Type"],
)


@app.get("/")
def root():
    return {"api": "AI Apps", "apps": ["chat", "bedtime"], "health": "/healthz"}


# --- App 1: Chat -------------------------------------------------------------

@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    answer = call_gemini(question)
    save_interaction(question, answer)
    return AskResponse(answer=answer, history=fetch_recent_history())


@app.get("/history", response_model=list[Interaction])
def history():
    return fetch_recent_history()


# --- App 2: Bedtime Story ----------------------------------------------------

@app.post("/story", response_model=StoryResponse)
def story(payload: StoryRequest):
    child_name = payload.child_name.strip()
    theme = payload.theme.strip()
    if not child_name:
        raise HTTPException(status_code=400, detail="Please enter the child's name.")
    if not theme:
        raise HTTPException(status_code=400, detail="Please say what the story is about.")
    text = generate_story(child_name, theme)
    save_story(child_name, theme, text)
    return StoryResponse(story=text, history=fetch_recent_stories())


@app.get("/stories", response_model=list[Story])
def stories():
    return fetch_recent_stories()


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
