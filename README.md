# AI Apps

One FastAPI project hosting two **single-turn** AI apps behind a hub page,
powered by the Gemini API and Postgres.

| # | App | Page | What it does |
|---|---|---|---|
| 1 | 💬 Chat | `/chat` | Ask a question, get a short answer. Every exchange is saved. |
| 2 | 🌙 Bedtime Story | `/bedtime` | A gentle ~200-word story built around a child's name and a theme. |

**Single-turn** means one request in, one answer out. The model never sees
earlier exchanges — the saved history is for *you* to read back, not context fed
into the prompt.

**Status:** working locally, verified end to end. Not yet deployed.

## Architecture

```
Browser  ──POST──►  FastAPI  ──httpx──►  Gemini API
                       │
                       └──psycopg──►  Postgres (one database, two tables)
```

FastAPI serves its own HTML, so there is one origin, no CORS, and one deploy.

```
app/
  main.py                  hub + both apps + /healthz
  database.py              DATABASE_URL + get_conn()
  schemas.py               chat models, then story models
  services/
    gemini_service.py      the only file that talks to Gemini
    chat_service.py        save_interaction / fetch_recent_history
    story_service.py       save_story / fetch_recent_stories
  templates/
    index.html             the hub
    chat.html              app 1
    story.html             app 2
  static/style.css
sql/
  001_create_interactions.sql
  002_create_stories.sql
scripts/smoke_gemini.py    exercises both apps without touching the database
render.yaml                Render Blueprint (web service + free Postgres)
.python-version            3.13 - Render reads this to pick the runtime
```

## Tech stack

Audited and upgraded 8 August 2026. All versions below verified working together.

| Layer | Choice | Version | Why |
|---|---|---|---|
| Language | Python | **3.13** | Pinned via `.python-version`. Render's default is now 3.14.3 — we pin so the runtime matches what's tested. |
| Web framework | FastAPI | `0.141.*` | Typed request/response validation at the boundary; serves the HTML too. |
| ASGI server | Uvicorn `[standard]` | `0.52.*` | `[standard]` adds `watchfiles` for `--reload` and `websockets`. |
| Templating | Jinja2 | `3.1.*` | Server-rendered pages; no frontend build step. |
| HTTP client | HTTPX | `0.28.*` | Calls the Gemini REST API. Same library FastAPI's test client uses. |
| Database driver | psycopg `[binary]` | `3.3.*` | Postgres 3.x driver. `[binary]` ships wheels, so no local C toolchain. |
| Config | python-dotenv | `1.2.*` | Loads `.env` in development. On Render the env vars are real. |
| Database | PostgreSQL | **16** | Docker locally; Render managed in production. |
| Model | Gemini | `gemini-3.6-flash` | Fast and cheap; set via `GEMINI_MODEL`, swappable without code changes. |
| Hosting | Render | free tier | Web service + managed Postgres, one account, no CORS. |

**No ORM, no migration tool, no test framework, no logging framework, no frontend
framework.** Plain SQL in two service files, plain `<script>` in two templates.
Every dependency above is load-bearing — see `CLAUDE.md` for the doctrine.

Pins are **minor-locked with a floating patch** (`0.141.*`): security fixes arrive
automatically, surprise API changes don't.

## Run it

**1. Start Postgres** (needs Docker Desktop running):

```bash
docker start ai-apps-pg
```

The container and the `ai_apps` database already exist. To rebuild from scratch:

```bash
docker run -d --name ai-apps-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ai_apps -p 5432:5432 postgres:16
docker exec -i ai-apps-pg psql -U postgres -d ai_apps < sql/001_create_interactions.sql
docker exec -i ai-apps-pg psql -U postgres -d ai_apps < sql/002_create_stories.sql
```

**2. Start the app:**

```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Open <http://localhost:8000>.

## Check it's healthy

```bash
curl http://localhost:8000/healthz     # {"gemini":true,"postgres":true}
```

If either says `false`, that's the half to fix. To test Gemini alone, with no
database involved:

```bash
python -m scripts.smoke_gemini
```

Expect ~2.5s for the chat answer and ~6–8s for a ~185-word story.

## See your saved conversations

Every question asked through the browser becomes a row:

```bash
docker exec ai-apps-pg psql -U postgres -d ai_apps \
  -c "SELECT id, question, created_at FROM interactions ORDER BY id DESC;"

docker exec ai-apps-pg psql -U postgres -d ai_apps \
  -c "SELECT id, child_name, theme, created_at FROM stories ORDER BY id DESC;"
```

Each row is a **complete, self-contained exchange** — question, answer, model,
timestamp. There is no thread linking one row to the next. That is the
single-turn design: a log of exchanges, not a conversation transcript.

Data survives `docker stop`/`docker start`. It is lost only on `docker rm`.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` | Hub — pick an app |
| `GET` | `/chat` | App 1 page |
| `POST` | `/ask` | `{question}` → `{answer, history[]}` |
| `GET` | `/history` | 10 most recent exchanges |
| `GET` | `/bedtime` | App 2 page |
| `POST` | `/story` | `{child_name, theme}` → `{story, history[]}` |
| `GET` | `/stories` | 10 most recent stories |
| `GET` | `/healthz` | `{"gemini": bool, "postgres": bool}` — always 200; a diagnostic, not a gate |

Errors: `400` blank input · `422` malformed body (Pydantic) · `502` Gemini or
Postgres unreachable.

## Configuration

`.env` — app runtime config, never committed:

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | From <https://aistudio.google.com/apikey> |
| `GEMINI_MODEL` | `gemini-3.6-flash` |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ai_apps` |

Read with `os.environ["..."]` at import time, so a missing one is a loud
`KeyError` at startup rather than a confusing failure later.

`.render.env` — **tooling only**, holds `RENDER_API_KEY`. The app never reads it
and it must never be deployed; that key can create, delete, and bill resources
across your whole Render account. Both files are gitignored (verified with
`git check-ignore`).

## Deploying to Render

`render.yaml` is written and the start command is tested. Remaining steps:

1. `git commit` — the repo is initialised and staged, not yet committed
2. Push to GitHub (Blueprint deploys read `render.yaml` **from a repo**, so a
   local commit is not enough)
3. Render → **New → Blueprint** → select the repo
4. Set `GEMINI_API_KEY` in the dashboard (it is `sync: false`, so it is
   deliberately absent from the committed file)
5. Apply both migrations to the managed database

⚠️ Render's free Postgres **expires 30 days after creation** — there is no reason
to create it before you actually deploy.

## Known limits

These are the honest edges of a single-turn, ungrounded app, not bugs:

- **No memory.** Ask the same question twice and you get the same answer; the
  model does not know it just replied.
- **No grounding.** Asked "who won the world cup" in August 2026, it named the
  2022 tournament — its training data ends earlier and nothing supplies current
  facts. Closing this needs retrieval or a search tool.
- **No clarifying questions.** An ambiguous prompt gets a hedged answer covering
  every interpretation, because there is no next turn in which to ask.

## Tuning the output

`CHAT_SYSTEM_PROMPT` and `STORY_SYSTEM_PROMPT` in
`app/services/gemini_service.py` shape the output far more than any code change.
Try predicting what an edit will do *before* running it, then compare — that gap
is where the learning is.

## Adding a third app

1. A system prompt constant in `gemini_service.py`
2. A `<name>_service.py` with save + fetch
3. Schemas in `schemas.py`
4. A template, and a card on the hub in `index.html`
5. A `sql/00N_create_<name>.sql`
6. Routes in `main.py`

Nothing else should need to change.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| New routes 404, edits do nothing, **no access-log lines** | A stale uvicorn worker is still serving the port | See `CLAUDE.md` → "Killing uvicorn by port leaves orphaned workers". Check reality with `curl localhost:8000/openapi.json` |
| `KeyError: 'GEMINI_API_KEY'` | No `.env` in the project root | `cp .env.example .env` and fill it in |
| `/healthz` shows `postgres: false` | Container not running | `docker start ai-apps-pg` |
| Request hangs ~10s then 502 | Postgres unreachable; Windows blackholes the closed port instead of refusing it | Start the container. `get_conn()` sets `connect_timeout=5` so this fails in seconds instead of forever |
| `ModuleNotFoundError: No module named 'app'` | Ran a script by path | `python -m scripts.smoke_gemini` from the project root |
| Render API returns bare `401` | Truncated API key paste | Keys are ~32–40 chars. Check the length first |
| `address already in use` | A previous server is still up | Kill it properly (see `CLAUDE.md`), or `--port 8001` |

## More

- `CLAUDE.md` — conventions, insights, and the full gotcha list
- `PRD.md` — scope, open decisions, milestones, risks
