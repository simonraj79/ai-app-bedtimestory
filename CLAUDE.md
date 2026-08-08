# CLAUDE.md — AI Apps

Read this before touching code. It records what this project is, the rules it is
built to, the insights worth keeping, and the gotchas that already cost time.

## What this is

One FastAPI project hosting **two single-turn AI apps** behind a hub page.
Gemini is the model; Postgres stores what was asked and answered.

| # | App | Page | Endpoint | Table |
|---|---|---|---|---|
| 1 | 💬 Chat | `/chat` | `POST /ask` | `interactions` |
| 2 | 🌙 Bedtime Story | `/bedtime` | `POST /story` | `stories` |

```
Browser  ──POST──►  FastAPI  ──httpx──►  Gemini API
                       │
                       └──psycopg──►  Postgres (one database, two tables)
```

One project, one database, one deploy. FastAPI serves its own HTML, so there is
no CORS and no second frontend host.

**This folder supersedes `D:\SINGLE TURN CHAT`.** Everything lives here.

## Layout

```
app/
  main.py                  hub + both apps + /healthz
  database.py              DATABASE_URL + get_conn()
  schemas.py               chat models, then story models
  services/
    gemini_service.py      the ONLY file that knows the model provider
    chat_service.py        save_interaction / fetch_recent_history
    story_service.py       save_story / fetch_recent_stories
  templates/
    index.html             the hub
    chat.html              app 1
    story.html             app 2
  static/style.css         shared; body.bedtime overrides the palette
sql/
  001_create_interactions.sql
  002_create_stories.sql
scripts/smoke_gemini.py    exercises both apps, no database involved
render.yaml                Render Blueprint (web service + free Postgres)
```

---

# Insights — the reasoning behind the shape

## Single-turn is a design decision, not an omission

Every request sends exactly `[systemInstruction, one user message]`. The model
never sees earlier exchanges. The tables are a **log for the human to read back**
— never fed into a prompt.

**This is observable in the data.** Rows 2 and 3 of `interactions` are the same
question asked twice, and the answers are near-identical: the model had no idea
it had just answered. If history were being fed back, the second answer would
have referenced the first.

Do not "helpfully" add conversation history. That is a different product with
different costs: session keys, token growth per turn, per-user isolation. If it
is wanted, make it a deliberate decision.

## The app is ungrounded, and that has visible consequences

Asked "who won the world cup" on 8 Aug 2026, the model named the **2022**
tournament as the most recent. Its training data ends before 2026 and nothing in
this app grounds it in the present. It also hedged across four different
tournaments rather than asking which sport — because there is no next turn in
which to receive the answer.

Neither is a bug. They are the honest shape of a single-turn, ungrounded app.
Closing the first gap means retrieval or a search tool; closing the second means
going multi-turn. Both are real features, not fixes.

## Provider isolation is the point

`main.py` knows only `call_gemini(question)` and
`generate_story(child_name, theme)`. Both funnel through one
`ask_gemini(system_prompt, message)` that owns the HTTP call. Everything
Gemini-shaped lives in one file — which is why moving from Ollama to Gemini
touched exactly one file. Let no Gemini-shaped detail leak into routes or
services.

**Adding a third app** means: a system prompt constant, a `*_service.py`,
schemas, a template, a hub card, and a `sql/00N_*.sql`. Nothing else changes.

## The system prompts are the product

`CHAT_SYSTEM_PROMPT` and `STORY_SYSTEM_PROMPT` in
`app/services/gemini_service.py` do more to shape output than any code. The story
prompt carries length, vocabulary, tone, safety rules, and the ending. Tuning it
is the highest-leverage change available — change it deliberately, then re-run
the smoke test.

Child-safety for app 2 lives entirely in that prompt. If illustrations are ever
added, they need their own safety pass — image models do not inherit it.

## `render.yaml` describes the deployment and contains zero secrets

Two mechanisms make that possible, and both are deliberate:

- `GEMINI_API_KEY` uses **`sync: false`** — "this variable exists, its value
  lives only in the dashboard." The blueprint is committed; the key never is.
- `DATABASE_URL` uses **`fromDatabase`** — Render injects the managed connection
  string at deploy time. You never see it, never copy it, and it cannot drift
  from the actual database.

## Two kinds of secret, two files

| File | Key | Who reads it |
|---|---|---|
| `.env` | `GEMINI_API_KEY` | The app, at runtime. **Gets uploaded to Render.** |
| `.render.env` | `RENDER_API_KEY` | Only tooling. **Never deployed.** |

`RENDER_API_KEY` creates, deletes, and bills resources across the whole account.
It landed in `.env` once, was exposed, and had to be rotated. Putting it there
uploads an account-wide admin key into the platform it controls.

---

# Coding rules

Inherited from the course's `AGENTS.md`, and they hold here:

- Simplicity over cleverness. The next reader must understand it in one pass.
- No custom exception classes. `HTTPException(status_code=..., detail="...")` is
  the whole error surface.
- No `BaseSettings` / `pydantic-settings` / config classes. Three
  `os.environ["..."]` reads at module load are clearer.
- No bare `except Exception` — catch the narrowest exception that names the
  failure (`httpx.HTTPError`, `psycopg.Error`).
- No helper called from exactly one place. (`ask_gemini` earns its place: two
  callers, and it removes a duplicated HTTP block.)
- No logging framework. No tests in V1.
- Comments explain *why*, never *what*.

**Fail loudly on config.** `os.environ["GEMINI_API_KEY"]` uses bracket access on
purpose. A missing variable is a `KeyError` at startup, not a confusing 500 an
hour later. Do not "fix" this with `.get(..., default)`.

---

# Gotchas — all of these actually happened

## Killing uvicorn by port leaves orphaned workers still serving

`uvicorn --reload` runs a reloader parent that spawns the real server through
`multiprocessing.spawn`. **The worker's command line contains no "uvicorn"** — it
reads `python -c "from multiprocessing.spawn import spawn_main; ..."`. So both of
these miss it:

```powershell
# WRONG - kills the listener; the parent respawns a replacement
Get-NetTCPConnection -LocalPort 8000 | Stop-Process
# WRONG - the worker's command line does not match "uvicorn"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match "uvicorn" }
```

The symptom is brutal: a **stale server keeps answering on port 8000** with old
code. New routes 404, edits appear to do nothing, and the uvicorn log shows
startup but *no access-log lines* — because requests are going elsewhere.

**Diagnose by asking the running app**, not by re-reading the file:

```bash
curl -s http://localhost:8000/openapi.json | python -c "import json,sys; print(sorted(json.load(sys.stdin)['paths']))"
```

**Kill properly** — match spawn children too:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match "uvicorn|spawn_main" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Then confirm the port is free before restarting. A listening socket attributed to
an already-dead PID means a child still holds the inherited handle.

## Windows blackholes closed ports — Postgres hangs forever

`localhost` resolves to `::1` first on Windows. When nothing is listening the
packet is **dropped, not refused** — so `psycopg.connect()`, which has no default
timeout, waits indefinitely. `/healthz` hung with no entry in the uvicorn log.

`get_conn()` sets `connect_timeout=5`. **Do not remove it.** On Render this
matters more: a hanging `/healthz` reads as "still starting" forever instead of
"database is down".

## `python scripts/foo.py` → `ModuleNotFoundError: No module named 'app'`

Running a script by path puts `scripts/` on `sys.path`, not the project root.
Use `python -m scripts.smoke_gemini` from the project root — `-m` puts the
current directory on the path. (`uvicorn app.main:app` works for the same reason.)

## `load_dotenv()` resolves relative to the calling file, not the shell's cwd

A throwaway script in a temp folder found no `.env` and died with `KeyError`,
even though the shell was `cd`'d into the project. For scripts outside the
project tree, pass the path explicitly.

## `load_dotenv()` must run before the imports that read `os.environ`

`app/main.py` calls it on line 3, above the service imports, and those imports
sit below it deliberately. Services read `os.environ[...]` **at module load**, so
moving them above `load_dotenv()` breaks startup. Ignore any linter that wants to
tidy the import order here.

## Verify `.gitignore` with git, not by reading it

Reading the file proves nothing. This does:

```bash
git check-ignore -v .env .render.env venv/
git add -A && git diff --cached --name-only    # what would actually be committed
```

Confirmed on 8 Aug 2026: `.env` (rule line 1), `.render.env` (line 3), `venv/`
(line 4) all excluded; 21 files staged, zero secrets among them.

## Render API keys: length is the tell

~32–40 characters. A **20-character** key is a truncated paste and returns
`401 {"message":"Unauthorized"}` — the message does not say "truncated", so check
the length first. Current key verified: 32 chars, owner
`tea-csps46i3esus73eojjp0` (Simon Raj's Workspace).

## Gemini API keys no longer start with `AIza`

This key starts with `AQ.A` and is 53 characters. The course docs
(`module5-readiness-checklist.md` §8) say `AIza...` — outdated, not a problem.
Both `?key=<KEY>` and the `x-goog-api-key` header work. We use the header.

## Gemini 3.x spends heavily on hidden thinking

A one-sentence request billed `thoughtsTokenCount: 428` against
`candidatesTokenCount: 38` — over 90% of output tokens invisible. Chat is ~2.5s;
a ~185-word story is ~6–8s. If that needs to be faster, this is where the time
goes.

## Response shape

`candidates[0].content.parts[0].text`. Parts may also carry `thoughtSignature`;
`finishReason: "STOP"` is the success case.

## Windows hides file extensions

The API key first arrived in `.env.txt`, not `.env` — `python-dotenv` would never
have found it. If a variable is mysteriously missing, check for a trailing `.txt`.

## PowerShell here-strings mangle quotes in inline Python

`python -c @'...'@` silently stripped the quotes from a URL and produced a
`SyntaxError`. Write the script to a file and run the file.

## Git on Windows rewrites line endings

`git add` warns `LF will be replaced by CRLF` on every text file. Harmless here —
there are no shell scripts. **If a `.sh` is ever added**, commit a
`.gitattributes` with `*.sh text eol=lf` first, or it will fail on Render's Linux
containers with `bad interpreter`.

## Postgres is not installed natively on this machine

`C:\Program Files\PostgreSQL\16` contains **only pgAdmin** — no `bin/`, no
`psql.exe`, no server service. Postgres runs in Docker:

```bash
docker start ai-apps-pg
```

Database `ai_apps` holds both tables. Data survives `docker stop`/`start`; it is
lost only on `docker rm`.

## Render free tier, before you deploy

- Free **Postgres expires 30 days after creation** — create it near launch.
- Free **web services sleep after 15 minutes** idle; the next request takes
  30–60s. Not a bug.
- Blueprint deploys read `render.yaml` **from a Git repo** — it must be pushed to
  GitHub first. A local commit is not enough.

---

# Verifying

```bash
curl http://localhost:8000/healthz     # {"gemini":true,"postgres":true}
python -m scripts.smoke_gemini         # both apps, Gemini only, no database

docker exec ai-apps-pg psql -U postgres -d ai_apps \
  -c "SELECT id, question, created_at FROM interactions ORDER BY id DESC;"
```

`/healthz` reports each dependency separately on purpose — it tells you *which*
half is broken. Keep it that way. Note it always returns **200**; it is a
diagnostic, not a gate.

# Current state — all verified 8 Aug 2026

`/` `/chat` `/bedtime` `/static/style.css` → 200 · `/healthz` →
`{"gemini":true,"postgres":true}` · `POST /ask` → 200, row in `interactions` ·
`POST /story` → 200, row in `stories` · blank input → 400 · malformed body → 422 ·
5 real conversations persisted from browser use · Render start command tested on
`0.0.0.0` · Render API key verified · git repo initialised, **staged not
committed**.
