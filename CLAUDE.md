# CLAUDE.md — AI Apps

Read this before touching code. It records what this project is, the rules it is
built to, the insights worth keeping, and the gotchas that already cost time.

## What this is

Two **single-turn** AI apps behind a hub page. A FastAPI **backend** (Render) and
a separate static **frontend** (Vercel), talking cross-origin.

| # | App | Page | Endpoint | Table |
|---|---|---|---|---|
| 1 | 💬 Chat | `chat.html` | `POST /ask` | `interactions` |
| 2 | 🌙 Bedtime Story | `story.html` | `POST /story` | `stories` |

```
Browser ──(static)──► Vercel: frontend/
   │
   └──(fetch, CORS)──► Render: FastAPI ──httpx──► Gemini API
                          │
                          └──psycopg──► Postgres (one DB, two tables)
```

**This folder supersedes `D:\SINGLE TURN CHAT`.** Everything lives here.

## Layout

```
app/                       the backend - API only, no HTML
  main.py                  CORS + routes + /healthz
  database.py              DATABASE_URL + get_conn()
  schemas.py               chat models, then story models
  services/
    gemini_service.py      the ONLY file that knows the model provider
    chat_service.py        save_interaction / fetch_recent_history
    story_service.py       save_story / fetch_recent_stories
frontend/                  the frontend - deployed to Vercel, static only
  index.html               hub
  chat.html                app 1
  story.html               app 2
  config.js                BACKEND_URL - the one line to change per environment
  style.css                body.bedtime overrides the palette
sql/
  001_create_interactions.sql
  002_create_stories.sql
scripts/smoke_gemini.py    exercises both apps, no database involved
render.yaml                Render Blueprint (web service + free Postgres)
Procfile                   Render start command
vercel.json                deploy frontend/ as static
.vercelignore              keep the Python backend away from Vercel
.python-version            3.13
```

## Live — deployed 8 Aug 2026

| | URL |
|---|---|
| **Frontend** | <https://ai-app-bedtimestory.vercel.app> |
| **Backend** | <https://ai-app-bedtimestory.onrender.com> |

| Thing | Value |
|---|---|
| GitHub repo | `simonraj79/ai-app-bedtimestory` (**private**) |
| Render owner | `tea-csps46i3esus73eojjp0` (Simon Raj's Workspace) |
| Render service | `srv-d9ra32qfngtc73ctjudg` · free · singapore · auto-deploy on `master` |
| Render Postgres | `dpg-d9ra1q2fngtc73ctho80-a` · free · singapore · PG 16.14 |
| **DB expires** | **2026-09-07** — free tier, 30 days from creation |
| Vercel team | `team_6Mc9jwQee8nmnfyfV8IJPAlx` (`simon-rajs-projects`) |
| Vercel project | `prj_IRlDJCZYjQNittWSAbm8cKJWle2O` (`ai-app-bedtimestory`) |
| Local Postgres | Docker container `ai-apps-pg`, database `ai_apps` |

**Vercel auto-deploy is NOT wired** (re-verified 8 Aug 2026 — `link: null`, and
the only deployment is a direct upload with no `githubCommitSha`). The frontend
was uploaded via the API because Vercel's GitHub App cannot see the private repo,
so **`git push` redeploys Render but not Vercel**. See the gotcha below for the
precise diagnosis and the two API checks that confirm it.

Until it is linked, redeploy the frontend with the upload script — it takes
seconds and is the only way a frontend change reaches production.

---

# Insights — the reasoning behind the shape

## Single-turn is a design decision, not an omission

Every request sends exactly `[systemInstruction, one user message]`. The model
never sees earlier exchanges. The tables are a **log for the human to read back**
— never fed into a prompt.

**Observable in the data.** Rows 2 and 3 of `interactions` are the same question
asked twice with near-identical answers: the model had no idea it had just
answered. If history were fed back, the second would have referenced the first.

Do not "helpfully" add conversation history. That is a different product with
different costs: session keys, token growth per turn, per-user isolation.

## The app is ungrounded, and that has visible consequences

Asked "who won the world cup" on 8 Aug 2026, the model named the **2022**
tournament as most recent. Its training data ends before 2026 and nothing here
grounds it in the present. It also hedged across four competitions rather than
asking which sport — because there is no next turn in which to receive an answer.

Neither is a bug. Closing the first means retrieval or a search tool; closing the
second means going multi-turn. Both are features, not fixes.

## CORS is a browser policy, not authentication

Verified locally: a preflight `OPTIONS` from a disallowed origin gets **400 with
no `access-control-allow-origin`**, so the browser never sends the real request.
That is why the course's documented failure is *"Failed to fetch" with nothing in
the backend logs* — people hunt through server code for a request that never
arrived.

But `curl` ignores CORS entirely. Anyone can still `POST /ask` from a terminal.
CORS stops **other people's websites** using your API through their visitors'
browsers; it does not stop a determined caller. Treating it as security is a
common and expensive misreading.

## The split deploy has a circular dependency

`frontend/config.js` needs the Render URL; the backend's `FRONTEND_ORIGINS` needs
the Vercel URL. Neither exists before the other deploys. The order is:

1. Deploy Render → get the backend URL
2. Set `BACKEND_URL` in `frontend/config.js`, commit
3. Deploy Vercel → get the frontend URL
4. Set `FRONTEND_ORIGINS` on Render to that URL

Two passes, unavoidable. A single-origin deploy (FastAPI serving its own
templates) removes this entirely — that was the trade accepted when matching the
course's architecture.

## The production database has no public surface at all

`DATABASE_URL` on Render uses the **internal** connection string
(`dpg-...-a/ai_apps`, no public hostname). Traffic never leaves Render's private
network: lower latency, and nothing internet-facing to attack.

The **external** string exists only for one-off admin work like migrations, and
even that is refused by default — `ipAllowList` is empty on a new database, so
external connections are dropped. It is currently `[]` again, having been opened
to a single `/32` for the schema migration and closed immediately after.

If you ever need external access: add your IP, do the work, remove it. Do not
leave `0.0.0.0/0` behind.

## Two GitHub integrations, two different outcomes

Render pulled the private repo without complaint; Vercel returned
`repo_not_found`. Nothing is "blocked" — they are simply **separate
authorisations**. Render's GitHub OAuth was granted during course setup; Vercel's
GitHub App was never installed on this repo.

The practical consequence is asymmetric deployment: **`git push` redeploys the
backend but not the frontend.** Until Vercel's app is granted access, frontend
changes need a manual API upload, and it is easy to end up with a frontend that
silently lags the backend.

## Provider isolation is the point

`main.py` knows only `call_gemini(question)` and
`generate_story(child_name, theme)`; both funnel through one
`ask_gemini(system_prompt, message)` owning the HTTP call. Moving from Ollama to
Gemini touched exactly one file. Let no Gemini-shaped detail leak outward.

**Adding a third app**: a system prompt constant, a `*_service.py`, schemas, a
frontend page, a hub card, a `sql/00N_*.sql`, routes. Nothing else.

## The frontend picks its own backend

`frontend/config.js` derives `BACKEND_URL` from `location.hostname` — localhost
talks to the local backend, anything else to production. Editing one line per
environment is exactly how `BACKEND_URL` typos and "works locally, broken in
production" happen, and the course's own gotcha list names it as a top student
failure. Deriving it removes the class of bug entirely.

Nothing secret may ever live in `frontend/` — every visitor can read it.

## The story page is designed for a tired parent in a dark room

Choices that look cosmetic but are not:

- **Suggestion chips.** A blank "what should it be about?" demands creativity at
  the worst possible moment. One tap beats an empty field.
- **The child's name is remembered** (`localStorage`). It does not change nightly.
- **A wait needs a pulse.** 6–9 seconds of silence reads as a hang, so the
  writing state rotates lines and, after 12s, explains the free-tier cold start.
- **Story type is 1.15rem at 1.8 line-height**, with A−/A+ persisted — this text
  gets read aloud in low light.
- **History is collapsed.** Ten full stories inline is roughly 1,800 words of
  scrolling on a phone.
- **Auto-scroll to the story**, or on a phone it lands below the fold and looks
  like nothing happened.

## The system prompts are the product

`CHAT_SYSTEM_PROMPT` and `STORY_SYSTEM_PROMPT` in
`app/services/gemini_service.py` do more to shape output than any code. Child
safety for app 2 lives entirely in its prompt — if illustrations are ever added,
they need their own pass, because image models do not inherit it.

## Committed config, zero secrets

- `render.yaml`: `GEMINI_API_KEY` uses **`sync: false`** ("exists, value lives in
  the dashboard"); `DATABASE_URL` uses **`fromDatabase`** so Render injects the
  managed connection string and it cannot drift.
- `frontend/config.js` holds only a public URL — never a key. Anything in
  `frontend/` is readable by every visitor.

## Three kinds of secret, three files

| File | Key | Who reads it |
|---|---|---|
| `.env` | `GEMINI_API_KEY` | The app at runtime. **Uploaded to Render.** |
| `.render.env` | `RENDER_API_KEY` | Tooling only. Never deployed. |
| `.vercel.env` | `VERCEL_TOKEN` | Tooling only. Never deployed. |

The control-plane keys create, delete and bill resources across whole accounts.
`RENDER_API_KEY` landed in `.env` once, was exposed, and had to be rotated.
**Deploy tokens are short-lived by design — revoke both once deployment is done.**

---

# Coding rules

Inherited from the course's `AGENTS.md`, and they hold here:

- Simplicity over cleverness. The next reader must understand it in one pass.
- No custom exception classes. `HTTPException(status_code=..., detail="...")`.
- No `BaseSettings` / `pydantic-settings` / config classes. `os.environ["..."]`
  reads at module load are clearer.
- No bare `except Exception` — catch the narrowest exception that names the
  failure (`httpx.HTTPError`, `psycopg.Error`).
- No helper called from exactly one place. (`ask_gemini` earns its place: two
  callers, removes a duplicated HTTP block.)
- No logging framework. No tests in V1.
- Comments explain *why*, never *what*.

**Fail loudly on config.** Bracket access on purpose — a missing variable is a
`KeyError` at startup, not a confusing 500 an hour later. Never `.get(..., default)`.

---

# Gotchas — all of these actually happened

## Killing uvicorn by port leaves orphaned workers still serving

`uvicorn --reload` spawns its real worker via `multiprocessing.spawn`, so **the
worker's command line contains no "uvicorn"** — it reads
`python -c "from multiprocessing.spawn import spawn_main; ..."`. Both of these
miss it:

```powershell
# WRONG - kills the listener; the parent respawns a replacement
Get-NetTCPConnection -LocalPort 8000 | Stop-Process
# WRONG - the worker's command line does not match "uvicorn"
... | Where-Object { $_.CommandLine -match "uvicorn" }
```

Symptom: a **stale server answers with old code**. New routes 404, edits do
nothing, and the uvicorn log shows startup but *no access-log lines*. It bit
twice — the second time after deleting `app/templates/`, where the stale worker
kept 500ing on templates that no longer existed.

**Diagnose by asking the running app**, never by re-reading the file:

```bash
curl -s http://localhost:8000/openapi.json | python -c "import json,sys; print(sorted(json.load(sys.stdin)['paths']))"
```

**Kill properly:**

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match "uvicorn|spawn_main|http.server" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Then confirm the port is free. A listening socket owned by a dead PID means a
child still holds the inherited handle.

## Port 3000 is taken by Docker Desktop on this machine

Held by `wslrelay.exe` and `com.docker.backend.exe`. **Do not kill them** — that
breaks Docker, and Postgres with it. The frontend dev server uses **5500**:

```bash
python -m http.server 5500 --directory frontend --bind 127.0.0.1
```

`FRONTEND_ORIGINS` in `.env` must match that port exactly, scheme included.

## Windows blackholes closed ports — Postgres hangs forever

`localhost` resolves to `::1` first; a closed port **drops** the packet rather
than refusing it, so `psycopg.connect()` — no default timeout — waits forever.
`/healthz` hung with no log entry at all.

`get_conn()` sets `connect_timeout=5`. **Do not remove it.** On Render it matters
more: a hanging `/healthz` reads as "still starting" rather than "database down".

## Render's Python version: use `.python-version`, not `PYTHON_VERSION`

Render's default is now **3.14.3** (services created after 11 Feb 2026), which
the course tooling does not support. Two mechanisms, and they differ:

- `PYTHON_VERSION` env var — demands a **fully qualified** patch (`3.13.5`).
  Breaks whenever that exact patch is unavailable.
- **`.python-version` file** — accepts `3.13` and takes the latest patch. ✅ used here.

## `python scripts/foo.py` → `ModuleNotFoundError: No module named 'app'`

Running by path puts `scripts/` on `sys.path`, not the project root. Use
`python -m scripts.smoke_gemini` from the root — `-m` adds the cwd.

## `load_dotenv()` resolves relative to the calling file, not the shell's cwd

A script in a temp folder found no `.env` and died with `KeyError` despite the
shell being `cd`'d into the project. Pass the path explicitly for outside scripts.

It must also run **before** the imports that read `os.environ` at module load —
which is why `app/main.py` has its imports below line 3. Ignore linters that want
to tidy that.

## Verify `.gitignore` with git, not by reading it

```bash
git check-ignore -v .env .render.env .vercel.env venv/
git ls-tree -r origin/master --name-only | grep -cE '\.env$|\.render\.env|\.vercel\.env'
```

## Secret scanners: match key *shape*, not prefixes

Scanning for `AQ\.A` and `rnd_` flagged `CLAUDE.md` — because it *documents* what
those prefixes are. A scanner that cries wolf on prose gets ignored, and an
ignored scanner catches nothing. Match length and character class instead:

```bash
git grep -nIE 'AQ\.[A-Za-z0-9_-]{20,}|rnd_[A-Za-z0-9]{20,}|vcp_[A-Za-z0-9]{20,}'
```

## Silence is not a passing test

`git ls-tree | grep | sed` returns **sed's** exit code, so `|| echo "PASS"` can
never fire. The check printed nothing and looked like it passed. Count matches
and assert on the number.

## Credential formats and quirks

| Key | Prefix | Length | Notes |
|---|---|---|---|
| Gemini | `AQ.A` | 53 | Course docs say `AIza` — outdated. `?key=` and `x-goog-api-key` both work; we use the header. |
| Render | `rnd_` | ~32–40 | A 20-char one is a truncated paste → bare `401 Unauthorized`, which does not say "truncated". |
| Vercel | `vcp_` | 60 | Shown **once** at creation. |

**Vercel token scope:** must be **All Projects** under the team. A token scoped to
one existing project cannot *create* a new project.

## Free-tier quota is the limit you actually hit — choose the model for it

`gemini-3.6-flash` allows **20 requests per minute** on the free tier. A burst of
testing exhausts it in under a minute and every call then fails.

**We run `gemini-3.5-flash-lite`: ~500 requests/day** — 25× the headroom, and
ample for a household. Quality is indistinguishable at this length: "just right"
lands at 201 words against a 200-word target.

It also spends **no hidden thinking tokens**. `gemini-3.6-flash` billed
`thoughtsTokenCount: 428` against `candidatesTokenCount: 38` on a one-sentence
request — over 90% invisible, and that is where its latency went.
`gemini-3.5-flash-lite` reports `thoughtsTokenCount: None`.

Swap models with the `GEMINI_MODEL` env var; no code changes. Update it in
**both** places — `.env` locally and the Render dashboard (or
`PUT /v1/services/<id>/env-vars/GEMINI_MODEL`).

## A quota error is not an outage — do not report it as one

Exceeding the quota returns **429**, which `raise_for_status()` collapses into a
generic failure, surfacing as *"Gemini is not reachable."* — wrong, and useless
to the person waiting. `ask_gemini` now checks for 429 **before**
`raise_for_status()` and returns *"Too many stories at once. Wait a moment and
try again."*

Because `model_name` is stored per row, a model switch is visible in the data:

```sql
SELECT model_name, count(*) FROM stories GROUP BY model_name;
```

## Render's Postgres refuses external connections — and the error lies

A fresh Render database has `ipAllowList: None`. Connecting from outside fails
with:

```
psycopg.OperationalError: connection failed:
  SSL connection has been closed unexpectedly
```

**Nothing is wrong with SSL.** Render drops unlisted connections mid-handshake,
and the TLS layer reports it as a closed connection. Chasing certificates or
`sslmode` here wastes an hour.

The fix, and the pattern to reuse for any future migration:

```bash
# 1. find your public IP
curl -s https://api.ipify.org
# 2. open to that IP only
curl -X PATCH -H "Authorization: Bearer $RENDER_API_KEY" -H "Content-Type: application/json" \
  https://api.render.com/v1/postgres/<db-id> \
  -d '{"ipAllowList":[{"cidrBlock":"<ip>/32","description":"temporary - migration"}]}'
# 3. run the migration (psycopg needs sslmode="require")
# 4. close it again
  -d '{"ipAllowList":[]}'
```

Migrations run through `psycopg` directly — there is no `psql` on this machine.

## Vercel cannot see a private GitHub repo by default

`POST /v11/projects` with `gitRepository` fails:

```
400 repo_not_found - The repository "..." couldn't be found.
```

The repo exists and the token is valid — Vercel's GitHub App simply cannot see
that repo. Creating the project *without* `gitRepository` works, and it can be
linked later with `POST /v9/projects/<name>/link`.

**`repo_not_found` is ambiguous** — it means the same thing whether the App is
not installed at all, or installed but not granted this repo. Two checks
distinguish them:

```bash
# Does ANY project link successfully? If yes, the App IS installed.
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects?teamId=$TEAM&limit=30" | ...
```

On this account `ai-chatgpt-dko6` is linked to `simonraj79/ai-chatgpt`, which
**proves the App is installed** — so the failure is repository *access*, not
installation. The dashboard's "Install the GitHub App" prompt is misleading in
that state.

Fix: <https://github.com/settings/installations> → Vercel → Configure →
*Repository access* → add the repo → **Save**. Granting it in GitHub and
connecting the project in Vercel are **two separate steps**; doing the first does
not do the second.

**Making the repo public does NOT fix this.** Vercel needs the App installed for
**webhooks** — that is what turns a push into a deploy. Public visibility solves
*reading* the code; the App solves *being told it changed*. Only the second gives
auto-deploy.

**Verify, never assume.** After any attempt, confirm with:

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects/ai-app-bedtimestory?teamId=$TEAM"   # link: null?
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v6/deployments?projectId=<id>&teamId=$TEAM"     # any githubCommitSha?
```

A deployment with no `meta.githubCommitSha` came from a direct upload, not Git.

**Workaround actually used:** direct file upload, no Git involved —
`POST /v13/deployments?teamId=<team>&forceNew=1` with
`files: [{file, data: <base64>, encoding: "base64"}]` and
`projectSettings: {framework, buildCommand, installCommand, outputDirectory: null}`.
`outputDirectory` must be `null` when files are uploaded at the deployment root,
even though the project and `vercel.json` say `frontend` — those apply to *Git*
builds, where the repo root is the deployment root.

It works and goes live in seconds, but **loses auto-deploy**. Re-run
`scripts/`-style upload after any frontend change until the repo is linked.

## Render API notes

Creating a web service needs a nested shape that is easy to get wrong:

```json
{"type":"web_service","name":"...","ownerId":"tea-...","repo":"https://github.com/...",
 "branch":"master","autoDeploy":"yes",
 "serviceDetails":{"env":"python","region":"singapore","plan":"free",
   "healthCheckPath":"/healthz",
   "envSpecificDetails":{"buildCommand":"...","startCommand":"..."}},
 "envVars":[{"key":"...","value":"..."}]}
```

Timings observed: Postgres ~70s from `creating` to `available`; the web service
~75s from create to `live`. Poll `/v1/services/<id>/deploys?limit=1` and stop on
`live | build_failed | update_failed | canceled`.

## Vercel API notes

- `?teamId=<team>` is required for team-owned resources, as a **query parameter**.
- Aliases are only present once `readyState` is `READY`. The production alias
  came out as `ai-app-bedtimestory.vercel.app` — matching the project name — but
  **do not assume it**; read it from the deployment and set `FRONTEND_ORIGINS`
  from what it actually returns, or CORS silently blocks the whole frontend.
- The dashboard's renderer intermittently times out under CDP screenshot
  automation; retry once, then fall back to doing it by hand.

## CSS specificity beats source order — `body.bedtime button` painted everything gold

`body.bedtime button` is specificity **(0,1,2)**. `.chip` is (0,1,0) and
`.segmented button` is (0,1,1). Both lose **no matter where they appear in the
file**, so every suggestion chip and every length button rendered in the selected
gold state.

The fix was to stop styling by element and scope the fill to its actual job:
`body.bedtime .primary`. When a "later" rule appears to be ignored, count
specificity before reordering anything.

Related: `python -m http.server` caches CSS. After a stylesheet change a normal
reload can show the old file — hard-reload (`Ctrl+Shift+R`) before concluding the
CSS is wrong.

## `Reloading...` in the uvicorn log does not mean it reloaded

WatchFiles logged `WARNING: WatchFiles detected changes ... Reloading...` and the
worker **never restarted** — `Started server process` still appeared exactly once
with no `Shutting down`. The old code served for another ten minutes while a new
429 handler sat in the file doing nothing.

Check the pair, not the promise:

```bash
grep -c "Started server process" <log>   # must increase on every reload
```

If it has not increased, kill by process (see the orphaned-workers gotcha) and
start again.

## Browser automation: element refs go stale after navigation

`find` returned `ref_5`/`ref_7`/`ref_8` for the story form; clicking and typing
against them reported **success** while the fields stayed empty — the screenshot
showed placeholder text, not input. The refs belonged to a pre-navigation
snapshot of the page.

Two rules that follow:

- After any navigation, re-`find` or use coordinates from a fresh screenshot.
- **Screenshot to confirm input landed before clicking submit.** A "Typed ..."
  success message is not evidence that the value reached the field.

## `pip list --outdated` lies about transitive pins

It reported `starlette 1.4.1` available while FastAPI 0.141 constrains it to
0.46.2. Upgrade the direct dependency and let it resolve; do not chase transitives.

The FastAPI **0.115 → 0.141** jump was verified safe: every route, both apps, and
all error paths still pass.

## Windows odds and ends

- **Hidden extensions.** The API key first arrived as `.env.txt`; `python-dotenv`
  would never have found it. If a variable is mysteriously missing, look for `.txt`.
- **PowerShell here-strings mangle quotes** in `python -c @'...'@` — it silently
  stripped quotes from a URL and produced a `SyntaxError`. Write a file instead.
- **Git rewrites line endings** (`LF will be replaced by CRLF`). Harmless — there
  are no shell scripts. If a `.sh` is ever added, commit `.gitattributes` with
  `*.sh text eol=lf` first, or it fails on Render's Linux containers.
- **Postgres is not installed natively.** `C:\Program Files\PostgreSQL\16`
  contains **only pgAdmin** — no `bin/`, no server. Use Docker:
  `docker start ai-apps-pg`. Data survives stop/start; lost only on `docker rm`.

## Render free tier

- Postgres **expires 30 days after creation** — create it at deploy time.
- Web services **sleep after 15 minutes** idle; next request takes 30–60s.
- Blueprints read `render.yaml` **from a GitHub repo** — a local commit is not
  enough; it must be pushed, and Render must have access.

---

# Verifying

```bash
# backend
curl http://localhost:8000/healthz          # {"gemini":true,"postgres":true}
python -m scripts.smoke_gemini              # both apps, no database

# frontend (separate origin, on purpose)
python -m http.server 5500 --directory frontend --bind 127.0.0.1

# CORS, allowed vs disallowed
curl -i -X OPTIONS http://localhost:8000/ask -H "Origin: http://localhost:5500" \
  -H "Access-Control-Request-Method: POST"   # 200 + access-control-allow-origin
curl -i -X OPTIONS http://localhost:8000/ask -H "Origin: https://evil.example.com" \
  -H "Access-Control-Request-Method: POST"   # 400, no allow-origin

# data
docker exec ai-apps-pg psql -U postgres -d ai_apps \
  -c "SELECT id, question, created_at FROM interactions ORDER BY id DESC;"
```

`/healthz` reports each dependency separately on purpose. It always returns
**200** — a diagnostic, not a gate.

# Current state — deployed and verified 8 Aug 2026

**Live in production**, exercised through a real browser, not just curl:

- Hub loads; its background `/healthz` succeeds cross-origin (no error banner)
- **Chat** — asked through the UI, answered, persisted (`interactions` id 1–2)
- **Bedtime Story** — Anaya + a lantern-carrying turtle → 179 words, correct
  tone, ends with the child asleep, persisted (`stories` id 1)
- Production CORS: Vercel origin → `200` + allow header; rogue origin → `400`
- Backend cold response `GET /` 0.10s; `POST /ask` 4.0s end to end

Locally: both servers run (backend `:8000`, frontend `:5500`), blank input → 400,
malformed body → 422, `python -m scripts.smoke_gemini` passes both apps.

**Outstanding:**

1. **Vercel ↔ GitHub link** — until then `git push` redeploys only the backend
2. **Revoke both deploy tokens** — no longer needed; the Render one was exposed
   earlier in the session
3. **2026-09-07** — free Postgres expires; `/healthz` will show `postgres: false`
