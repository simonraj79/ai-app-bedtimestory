import os
import httpx
from fastapi import HTTPException

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ["GEMINI_MODEL"]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_URL = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent"

CHAT_SYSTEM_PROMPT = (
    "You are a concise, helpful assistant. "
    "Answer in one short paragraph (under 80 words). "
    "If you don't know, say so plainly."
)

STORY_SYSTEM_PROMPT = (
    "You are a warm, gentle bedtime storyteller for young children. "
    "Write a calm story of about 200 words with a beginning, a middle and a happy ending. "
    "Use simple words a five-year-old understands and short sentences. "
    "Never include anything frightening, sad or violent. "
    "End with the child safe, warm and falling asleep."
)


def ask_gemini(system_prompt: str, message: str) -> str:
    """One system prompt, one user message, one answer. No conversation history."""
    try:
        with httpx.Client(timeout=90.0) as client:
            r = client.post(GEMINI_URL, headers={"x-goog-api-key": GEMINI_API_KEY}, json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": message}]}],
            })
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Gemini is not reachable.")


def call_gemini(question: str) -> str:
    return ask_gemini(CHAT_SYSTEM_PROMPT, question)


def generate_story(child_name: str, theme: str) -> str:
    return ask_gemini(
        STORY_SYSTEM_PROMPT,
        f"Write tonight's bedtime story for a child named {child_name}, about {theme}.",
    )
