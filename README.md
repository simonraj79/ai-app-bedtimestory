# AI Apps

Two **single-turn** AI apps behind a hub page — a FastAPI backend on Render, a
static frontend on Vercel, Gemini for the model, Postgres for the record.

| # | App | Page | What it does |
|---|---|---|---|
| 1 | 💬 Chat | `chat.html` | Ask a question, get a short answer. Every exchange is saved. |
| 2 | 🌙 Bedtime Story | `story.html` | A gentle ~200-word story built around a child's name and a theme. |

**Single-turn** means one request in, one answer out. The model never sees
earlier exchanges — the saved history is for *you* to read back, not context fed
into the prompt.

## 🚀 Live

| | |
|---|---|
| **App** | <https://ai-app-bedtimestory.vercel.app> |
| **API** | <https://ai-app-bedtimestory.onrender.com> |
| Health | <https://ai-app-bedtimestory.onrender.com/healthz> |

Deployed 8 August 2026 and verified in a real browser: both apps answer, both
persist to Postgres, CORS allows the Vercel origin and refuses others.

> **⚠️ The free Postgres expires 2026-09-07.** After that `/healthz` reports
> `postgres: false` and writes fail.
>
> **⚠️ Vercel is not linked to GitHub.** `git push` redeploys the **backend
> only**. Frontend changes need a manual upload — see *Deploying* below.
>
> **⏳ First request after 15 minutes idle takes 30–60s** — Render's free tier
> sleeps. The page loads instantly (CDN); only the first API call waits.

## Architecture

```
Browser ──(static files)──► Vercel:  frontend/
   │
   └──(fetch, cross-origin)──► Render:  FastAPI ──httpx──► Gemini API
                                  │
                                  └──psycopg──► Postgres (one DB, two tables)
```

The frontend and backend are **separate deployments on separate origins**, which
is why CORS matters here. `frontend/config.js` derives the backend URL from the
hostname, so there is nothing to edit when moving between local and production.

```
app/                       backend - API only, no HTML
  main.py                  CORS + routes + /healthz
  database.py              DATABASE_URL + get_conn()
  schemas.py               chat models, then story models
  services/
    gemini_service.py      the only file that talks to Gemini
    chat_service.py        save_interaction / fetch_recent_history
    story_service.py       save_story / fetch_recent_stories
frontend/                  frontend - static, deploys to Vercel
  index.html  chat.html  story.html
  config.js                BACKEND_URL - auto-detected per environment
  style.css
sql/001_create_interactions.sql
sql/002_create_stories.sql
scripts/smoke_gemini.py    exercises both apps without touching the database
render.yaml  Procfile      Render deploy
vercel.json  .vercelignore Vercel deploy
.python-version            3.13
```

## Tech stack

Audited and upgraded 8 August 2026. All versions verified working together.

| Layer | Choice | Version | Why |
|---|---|---|---|
| Language | Python | **3.13** | Pinned via `.python-version`. Render's default is now 3.14.3; we pin so the runtime matches what's tested. |
| Web framework | FastAPI | `0.141.*` | Typed validation at the boundary. API only — it serves no HTML. |
| ASGI server | Uvicorn `[standard]` | `0.52.*` | `[standard]` adds `watchfiles` for `--reload`. |
| HTTP client | HTTPX | `0.28.*` | Calls the Gemini REST API. |
| Database driver | psycopg `[binary]` | `3.3.*` | `[binary]` ships wheels — no local C toolchain. |
| Config | python-dotenv | `1.2.*` | Loads `.env` in development. On Render the env vars are real. |
| Database | PostgreSQL | **16** | Docker locally; Render managed in production. |
| Model | Gemini | `gemini-3.5-flash-lite` | ~500 requests/day on the free tier (vs 20/min for `3.6-flash`), no hidden thinking tokens. Set via `GEMINI_MODEL`. |
| Frontend | Plain HTML + CSS + vanilla JS | — | No build step, no framework, no bundler. |
| Backend host | Render | free tier | Web service + managed Postgres. |
| Frontend host | Vercel | free tier | Static, from `frontend/`. |

**No ORM, no migration tool, no test framework, no logging framework, no frontend
framework, and no Jinja2** — the frontend is static and deploys separately.

Pins are **minor-locked with a floating patch** (`0.141.*`): security fixes arrive
automatically, surprise API changes don't.

## Run it locally

You need **two** servers, because production has two origins and you want local
to fail the same way production would.

**1. Postgres** (needs Docker Desktop running):

```bash
docker start ai-apps-pg
```

First time only:

```bash
docker run -d --name ai-apps-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ai_apps -p 5432:5432 postgres:16
docker exec -i ai-apps-pg psql -U postgres -d ai_apps < sql/001_create_interactions.sql
docker exec -i ai-apps-pg psql -U postgres -d ai_apps < sql/002_create_stories.sql
```

**2. Backend** — terminal one:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**3. Frontend** — terminal two:

```powershell
python -m http.server 5500 --directory frontend --bind 127.0.0.1
```

Open <http://localhost:5500>.

> Port **5500**, not 3000 — Docker Desktop holds 3000 on this machine.
> `FRONTEND_ORIGINS` in `.env` must match exactly, scheme and port included.

## Check it's healthy

```bash
curl http://localhost:8000/healthz     # {"gemini":true,"postgres":true}
python -m scripts.smoke_gemini         # Gemini only, no database
```

Expect ~2.5s for a chat answer, ~6–8s for a story.

## See your saved conversations

```bash
docker exec ai-apps-pg psql -U postgres -d ai_apps \
  -c "SELECT id, question, created_at FROM interactions ORDER BY id DESC;"

docker exec ai-apps-pg psql -U postgres -d ai_apps \
  -c "SELECT id, child_name, theme, created_at FROM stories ORDER BY id DESC;"
```

Each row is a **complete, self-contained exchange** — question, answer, model,
timestamp. Nothing links one row to the next. That's the single-turn design: a
log of exchanges, not a conversation transcript.

Data survives `docker stop`/`start`; lost only on `docker rm`.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` | JSON banner — confirms the API is up |
| `POST` | `/ask` | `{question}` → `{answer, history[]}` |
| `GET` | `/history` | 10 most recent exchanges |
| `POST` | `/story` | `{child_name, theme, length?}` → `{story, history[]}`. `length` is `short` \| `medium` \| `long`, defaulting to `medium`. |
| `GET` | `/stories` | 10 most recent stories |
| `GET` | `/healthz` | `{"gemini": bool, "postgres": bool}` — always 200; a diagnostic, not a gate |

Errors: `400` blank input or unknown length · `422` malformed body (Pydantic) ·
`429` free-tier quota exceeded · `502` Gemini or Postgres unreachable.

### Built for a tired parent in a dark room

Choices in `story.html` that look cosmetic but are not: one-tap **suggestion
chips** (a blank "what should it be about?" is the worst thing to face at 8pm);
the child's name **remembered** between nights; a **Short / Just right / Longer**
control; an animated **writing** state that explains the cold start after 12s;
the story set at **1.15rem / 1.8 line-height** with a persisted **A− / A+**
toggle for reading aloud; **auto-scroll** to the story; and **collapsed history**,
because ten full stories inline is ~1,800 words of scrolling on a phone.

## Configuration

`.env` — backend runtime config, never committed:

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | From <https://aistudio.google.com/apikey> |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ai_apps` |
| `FRONTEND_ORIGINS` | Comma-separated origins allowed to call the API |

Read with `os.environ["..."]` at import time, so a missing one is a loud
`KeyError` at startup rather than a confusing failure later.

`frontend/config.js` — `BACKEND_URL` is **auto-detected** from the hostname:
localhost talks to the local backend, anything else to production. Nothing to
edit per environment. Public by definition; **never put a key in `frontend/`** —
every visitor can read it.

`.render.env` and `.vercel.env` — **tooling only**. They hold account-wide
control-plane keys, are gitignored, and must never be deployed. Revoke both once
deploying is finished.

## Deploying

### Backend — automatic ✅

`git push origin master` redeploys Render. Nothing else to do.

### Frontend — manual, until Vercel is linked ⚠️

Vercel's GitHub App cannot see this private repo, so pushes do **not** redeploy
the frontend. Upload it directly instead:

```powershell
python scripts\deploy_frontend.py
```

**To fix it properly** (then pushes deploy both halves):
<https://github.com/settings/installations> → **Vercel** → **Configure** →
*Repository access* → add `ai-app-bedtimestory` → **Save**. Then connect the
project in Vercel → Project → Settings → Git.

Those are **two separate steps** — granting access in GitHub does not connect the
project in Vercel. Confirm it actually worked:

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects/ai-app-bedtimestory?teamId=$TEAM"
# "link" must be an object, not null
```

Making the repo public will **not** fix it — Vercel needs the App for webhooks,
which is what turns a push into a deploy.

### If you ever rebuild from scratch

⚠️ **Circular dependency.** The frontend needs the backend's URL; the backend's
CORS needs the frontend's URL. Neither exists first, so it takes two passes:

1. **Render** — create the service + Postgres, set `GEMINI_API_KEY`, apply both
   migrations. Note the backend URL.
2. Set `BACKEND_URL` in `frontend/config.js`, commit, push.
3. **Vercel** — deploy. Read the production alias from the response; don't assume
   it.
4. Set `FRONTEND_ORIGINS` on Render to that alias. Redeploy.

Render's Postgres refuses external connections by default (`ipAllowList: []`),
and reports it as `SSL connection has been closed unexpectedly`. To run
migrations: add your IP as a `/32`, migrate, remove it. See `CLAUDE.md`.

⚠️ Render's free Postgres **expires 30 days after creation**. Don't create it
before you actually deploy.

## Known limits

Honest edges of a single-turn, ungrounded app — not bugs:

- **No memory.** The same question twice gives the same answer; the model doesn't
  know it just replied.
- **No grounding.** Asked "who won the world cup" in August 2026, it named the
  2022 tournament. Its training data ends earlier and nothing supplies current
  facts.
- **No clarifying questions.** Ambiguous prompts get hedged answers covering every
  interpretation, because there's no next turn in which to ask.

## Tuning the output

`CHAT_SYSTEM_PROMPT` and `STORY_SYSTEM_PROMPT` in
`app/services/gemini_service.py` shape the output far more than any code change.
Predict what an edit will do *before* running it, then compare — that gap is
where the learning is.

## Adding a third app

1. A system prompt constant in `gemini_service.py`
2. A `<name>_service.py` with save + fetch
3. Schemas in `schemas.py`
4. A page in `frontend/`, and a card on the hub in `frontend/index.html`
5. A `sql/00N_create_<name>.sql`
6. Routes in `main.py`

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to fetch` in the browser, **nothing in the backend log** | CORS blocked the preflight — the request never arrived | Check `FRONTEND_ORIGINS` matches the frontend origin exactly, scheme and port included |
| New routes 404, edits do nothing, **no access-log lines** | A stale uvicorn worker is still serving | See `CLAUDE.md` → orphaned workers. Check reality with `curl localhost:8000/openapi.json` |
| `KeyError: 'GEMINI_API_KEY'` | No `.env` in the project root | `cp .env.example .env` and fill it in |
| `/healthz` shows `postgres: false` | Container not running | `docker start ai-apps-pg` |
| Request hangs ~10s then 502 | Postgres unreachable; Windows blackholes the closed port | Start the container. `connect_timeout=5` makes this fail in seconds, not forever |
| `ModuleNotFoundError: No module named 'app'` | Ran a script by path | `python -m scripts.smoke_gemini` from the project root |
| Frontend server won't start on 3000 | Docker Desktop holds that port | Use 5500 |
| Render/Vercel API returns bare `401` | Truncated token paste | Render ~32–40 chars, Vercel 60 |

## More

- `CLAUDE.md` — conventions, insights, and the full gotcha list
- `PRD.md` — scope, open decisions, milestones, risks
