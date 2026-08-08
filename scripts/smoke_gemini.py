"""Prove both apps' Gemini calls work, with no database involved.

Run from the project root:  python -m scripts.smoke_gemini
"""
import time
from dotenv import load_dotenv

load_dotenv()

from app.services.gemini_service import GEMINI_MODEL, call_gemini, generate_story

print(f"model: {GEMINI_MODEL}\n")

start = time.time()
answer = call_gemini("In one sentence, what is a web server?")
print(f"--- chat        {time.time() - start:.1f}s ---")
print(answer)

start = time.time()
story = generate_story("Maya", "a sleepy dragon who lost his slippers")
print(f"\n--- story       {time.time() - start:.1f}s, {len(story.split())} words ---")
print(story)
