# CLAUDE.md — AI Apps

Read this before touching code. It records what this project is, the rules it is
built to, the insights worth keeping, and the gotchas that already cost time.

## What this is

Two **single-turn** AI apps behind a hub page, plus an owner-only usage page. A
FastAPI **backend** (Render) and a separate static **frontend** (Vercel), talking
cross-origin. **Google sign-in is required to generate anything.**

| # | App | Page | Endpoints | Table | Who |
|---|---|---|---|---|---|
| 1 | 💬 Chat | `chat.html` | `POST /ask` · `GET /history` | `interactions` | any signed-in user |
| 2 | 🌙 Bedtime Story | `story.html` | `POST /story` · `GET /stories` | `stories` | any signed-in user |
| — | 📊 Usage | `admin.html` | `GET /admin/usage` | reads all three | `ADMIN_EMAIL` only |

`GET /` and `GET /healthz` are the only open routes. Everything else needs
`Authorization: Bearer <google-id-token>`, and history is **per user**.

```
                     ┌──(GIS)──► Google: sign in, get an ID token (JWT)
                     │
Browser ──(static)──►┤ Vercel: frontend/
   │                 │
   └──(fetch, CORS, Authorization: Bearer <jwt>)──► Render: FastAPI
                          ├──httpx───────► Gemini API
                          ├──google-auth─► Google certs (verify the signature)
                          └──psycopg────► Postgres (one DB, three tables)
```

**This folder supersedes `D:\SINGLE TURN CHAT`.** Everything lives here.

## Layout

```
app/                       the backend - API only, no HTML
  main.py                  CORS + routes + /healthz
  database.py              DATABASE_URL + get_conn()
  schemas.py               chat models, story models, CurrentUser, usage models
  services/
    gemini_service.py      the ONLY file that knows the model provider
    auth_service.py        the ONLY file that knows the identity provider
    chat_service.py        save_interaction / fetch_recent_history
    story_service.py       save_story / fetch_recent_stories
    admin_service.py       fetch_usage - totals, per-person counts, recent feed
frontend/                  the frontend - deployed to Vercel, static only
  index.html               hub
  chat.html                app 1
  story.html               app 2
  admin.html               usage - NOT linked from the hub, owner only
  config.js                BACKEND_URL + escapeHtml + the whole sign-in client
  style.css                body.bedtime overrides the palette
sql/
  001_create_interactions.sql
  002_create_stories.sql
  003_create_users.sql     one row per Google account, keyed on google_sub
  004_add_user_id.sql      nullable user_id on both tables + (user_id, id DESC)
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
| Google Cloud project | `dsai-mod-2-group-project` · number `722888382160` |
| OAuth client | Web application, in that project — **console-only**, see the gotcha |
| `ADMIN_EMAIL` | `simoraj@gmail.com` |
| Local Postgres | Docker container `ai-apps-pg`, database `ai_apps` |

⚠️ **The OAuth client is owned by `simoraj@gmail.com`, which is *not* the Chrome
default profile (`inspiring.resilience@gmail.com`).** Creating the client under
one account and then signing into the app with the other is an easy mistake and a
confusing one: the sign-in succeeds, the app works, and `/admin/usage` returns
`403` because the signed-in email is not `ADMIN_EMAIL`. Check which profile the
browser picked before debugging anything.

✅ **Vercel auto-deploy IS wired** — re-verified 8 Aug 2026 against the API, not
the dashboard:

```
link:  github -> simonraj79/ai-app-bedtimestory
latest deployment: READY  sha=c30bfce3  "Trigger first Vercel build ..."
```

A deployment carrying a `githubCommitSha` is the proof; the two below it have
`sha=NONE`, which is what the old manual uploads look like. **`git push` now
deploys both halves.** The gotcha below is kept because the `repo_not_found`
diagnosis is reusable, not because the link is still missing.

---

# Insights — the reasoning behind the shape

## ⭐ Assert on state, never on a system's report of itself

**The single most useful habit in this project.** Every expensive bug here shared
one shape: something *claimed* success, and the claim was false. Not one of them
produced an error.

| The claim | The reality | What actually settled it |
|---|---|---|
| `Reloading...` in the uvicorn log | The worker never restarted | `grep -c "Started server process"` — still 1 |
| `Typed "Anaya"` from browser automation | The field was empty; the ref was stale | A screenshot before clicking submit |
| `cmd \| grep \| sed` printed nothing, so "no secrets" | The pipeline returned **sed's** exit code, so `\|\| echo PASS` was unreachable | `grep -c` and compare the number |
| Vercel "linked to GitHub" | `link: null`, and the only deployment was a manual upload | Listing **all** projects — a sibling *was* linked, which located the real cause |
| Postgres `SSL connection closed unexpectedly` | Nothing wrong with SSL; the IP was not allow-listed | Reading `ipAllowList` from the API |
| "CORS keeps the history private" | `curl /stories` with no token and no `Origin` returned **200 and 3,099 bytes** of every child's name, theme and full story | One `curl` from a terminal, which ignores CORS entirely |
| "No OAuth client exists — the sweep found nothing" | Consumer OAuth clients are **console-only**; the CLI cannot see them at all | Opening `console.cloud.google.com/apis/credentials` |

The corrective in each case was the same: **query independent state.**
`curl /openapi.json` for what the server really serves. A row count for what was
really written. `git check-ignore -v` for what git really excludes. A screenshot
for what the page really contains.

Two rules that follow:

1. **A check that cannot fail is not a check.** Before trusting a safety check,
   make it fail on purpose. If you can't, you have a comment.
2. **Silence is not success.** Assert on a number, not on the absence of output.

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

## …and the misreading had already leaked every story

Not hypothetical. Before sign-in existed, from a terminal, no token, no `Origin`
header:

```bash
curl -s https://ai-app-bedtimestory.onrender.com/stories | wc -c   # 200, 3099
```

3,099 bytes: every child's name, every theme, every full story, to anyone who
guessed the route. The CORS config was correct the whole time and was never
capable of stopping it. **This is what "CORS is not authentication" costs when
it is left as a note rather than acted on.**

Per-user history closed it. `/stories` and `/history` now take the caller's
`user_id` from the verified token and query `WHERE user_id = %s`, so there is no
"all rows" read path left in the codebase to be reached.

## Sign-in is an ID token, not a session — the two origins decided it

Google Identity Services hands the **browser** a signed JWT. The browser sends it
as `Authorization: Bearer <jwt>`; `auth_service.py` verifies the signature
against Google's public keys. That is the whole mechanism. **No client secret, no
redirect URI, no callback route, no cookie, no session store.**

This was not the default choice — it was forced by the split deploy:

| Approach | Why not here |
|---|---|
| Session cookie | The frontend is `vercel.app` and the backend is `onrender.com` — **different registrable domains, both on the Public Suffix List**, so no cookie can be scoped to cover both. It would be a third-party cookie, which Safari blocks outright. The app would work in Chrome and silently fail on the exact device a parent uses at bedtime. |
| Authorization-code flow | Needs a **client secret** and a server-side callback. The secret cannot live in `frontend/` (every visitor reads it), and adding a callback route means state, redirect-URI registration and a session to put the result in — all to end up knowing the same thing the ID token already states. |

So the property "nothing secret may ever live in `frontend/`" survives sign-in
intact: `GOOGLE_CLIENT_ID` ships in `config.js` and is **public by design** — it
names the app to Google and rides in every sign-in request. It is not a
credential, and there is no secret counterpart in this flow.

The trade is stated in the gotchas: verification costs one outbound HTTPS call
per authenticated request, because google-auth does not cache Google's certs.

## Signed out, the page still renders — the button is just disabled

Sign-in is **required to generate**. It is not required to see the page. Every
page ships in the signed-out state with the submit button `disabled` and a hint
next to the Google button (*"Sign in with Google to hear a story."*).

Hiding the form instead would have been less code. It also reads as a broken
page — a parent who opens the app and finds nothing there does not conclude
"I must be signed out", they conclude the app is down.

The frontend never decides *who* you are, only *whether* to bother asking.
`decodeJwtPayload` in `config.js` reads the JWT payload without verifying
anything, and is for **display only** — greeting you by name. Branch on it for
permission and the admin page becomes a text field. The only authority on
identity is the backend's signature check.

## What sign-in did to the data model

Three decisions, each of which would be expensive to reverse:

- **`users` is keyed on `google_sub`, not email.** The `sub` claim is stable for
  the life of the Google account; an email address can be changed by its owner.
  Keyed on email, a rename forks one person into two rows and splits their
  history between them — silently, and unrecoverably without manual merging.
- **`user_id` is NULLABLE.** The 3 stories and 3 interactions already in
  production predate sign-in and have no owner, and never will. `NOT NULL` would
  have required inventing one, which is a lie written into the data. `NULL` says
  *"predates sign-in"*, and `admin_service.py` labels those rows
  `(before sign-in)` rather than dropping them, so the totals and the feed agree.
- **No events or analytics table.** `stories` and `interactions` already record
  what people do, with timestamps; `users.last_seen_at` is maintained by the same
  upsert that authenticates, so return visits are covered for free. A third table
  would duplicate rows that already exist in order to count them. See *Reading
  the tracking data* for the queries this makes possible.

`admin.html` is deliberately **not linked from the hub**. That is tidiness, not
security — the backend refuses `/admin/usage` to everyone but `ADMIN_EMAIL`
regardless of who finds the URL.

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

`auth_service.py` is the same idea for identity: `main.py` knows only
`Depends(current_user)` and `Depends(admin_user)`, and nothing Google-shaped —
`id_token`, `TransportError`, `google_sub` — appears anywhere else in the
backend.

**Adding a third app**: a system prompt constant, a `*_service.py`, schemas, a
frontend page, a hub card, a `sql/00N_*.sql`, routes. Nothing else. The routes
take `user: CurrentUser = Depends(current_user)` and the table gets a nullable
`user_id`, or the new app is the one that leaks.

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
- `frontend/config.js` holds only a public URL and the public OAuth client ID —
  never a key. Anything in `frontend/` is readable by every visitor.

`GOOGLE_CLIENT_ID` and `ADMIN_EMAIL` are also `sync: false`, but **neither is a
secret in the way `GEMINI_API_KEY` is**, and it matters that nobody treats them
as one:

| Variable | What it actually is |
|---|---|
| `GEMINI_API_KEY` | A **credential**. Leaked, it bills and is abused. Rotate on exposure. |
| `GOOGLE_CLIENT_ID` | **Public by design.** It ships in `frontend/config.js` and rides in every sign-in request. Its job is to be the value the token's `aud` claim is checked against — a *wrong* one silently rejects every sign-in, which is the real failure mode. Nothing to protect. |
| `ADMIN_EMAIL` | Merely **private**. A personal address kept out of a git repo, not a credential. Knowing it grants nothing: you still need a Google token proving you own it. |

`sync: false` on the last two means *"set this per environment"*, not
*"protect this"*. Both are read with bracket access, so a missing one is a
`KeyError` at startup rather than a deployment where every sign-in 401s.

## Three kinds of secret, three files

| File | Key | Who reads it |
|---|---|---|
| `.env` | `GEMINI_API_KEY` | The app at runtime. **Uploaded to Render.** |
| `.render.env` | `RENDER_API_KEY` | Tooling only. Never deployed. |
| `.vercel.env` | `VERCEL_TOKEN` | Tooling only. Never deployed. |

The control-plane keys create, delete and bill resources across whole accounts.
`RENDER_API_KEY` landed in `.env` once, was exposed, and had to be rotated.
**Deploy tokens are short-lived by design — rotate or revoke both once deployment
is done.** ✅ Both rotated 8 Aug 2026. Once each host deploys from Git, no code
reads these at all: `VERCEL_TOKEN`'s only consumer was `deploy_frontend.py`,
deleted at milestone 13. A token nothing reads is pure liability — revoke it.

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

## ⚠️ THE EXPENSIVE ONE: the running server is not the code you just wrote

**This has cost more time than every other bug in this project combined — three
separate incidents, hours in total.** Read this before debugging anything that
"should work".

Every time, the story was the same: the code on disk was **correct**, and the
process answering requests was running **something else**.

### The three incidents

| Symptom | What was actually true |
|---|---|
| `/bedtime` 404 while `/chat` 200, from a `main.py` defining both | A stale worker was serving; killing by port only killed the listener and the reloader respawned it |
| `GET /` 500 and `OPTIONS` 405 after deleting `app/templates/` | Same stale worker, now failing on templates that no longer existed |
| A new 429 handler had no effect for ~10 minutes | uvicorn logged `Reloading...` and **the worker never restarted** |

### Why the usual kills miss

`uvicorn --reload` runs a reloader parent that spawns the real worker through
`multiprocessing.spawn`. **The worker's command line contains no "uvicorn"** — it
reads `python -c "from multiprocessing.spawn import spawn_main; ..."`. So both of
these silently fail:

```powershell
# WRONG - kills the listener; the parent immediately respawns a replacement
Get-NetTCPConnection -LocalPort 8000 | Stop-Process
# WRONG - the worker's command line does not match "uvicorn"
... | Where-Object { $_.CommandLine -match "uvicorn" }
```

### `Reloading...` is a claim, not a confirmation

The third incident is the nastiest, because the log **says it worked**:

```
WARNING:  WatchFiles detected changes in 'app\services\gemini_service.py'. Reloading...
```

…and nothing restarted. The proof is the pair of lines, not the promise:

```bash
grep -c "Started server process" <log>   # must INCREASE on every reload
grep -c "Shutting down" <log>            # should appear alongside it
```

One `Started server process` and no `Shutting down` after a `Reloading...` means
the old process is still serving. There is no error anywhere.

### The three tells

1. **No access-log lines** for requests you know you just made → a different
   process is answering.
2. **`Reloading...` with no new `Started server process`** → the reload didn't happen.
3. **A listening socket owned by a dead PID** → a child still holds the inherited
   handle.

### What to do instead

**Ask the running system what it is, never re-read the file:**

```bash
curl -s http://localhost:8000/openapi.json \
  | python -c "import json,sys; print(sorted(json.load(sys.stdin)['paths']))"
```

**Kill properly — match spawn children, then confirm the port is free:**

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match "uvicorn|spawn_main|http.server" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

**When a change must be verified, prefer no `--reload` at all.** Start the server
fresh for the test run. A deterministic restart costs three seconds; a phantom
reload cost ten minutes and a wrong diagnosis.

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

## `google-auth` alone does not install what it imports

`google.auth.transport.requests` imports the **`requests`** package. This project
has never had it — it uses httpx — and bare `google-auth` does not pull it in.
The failure is at **import**, so the backend does not start at all: not a 500 on
a sign-in attempt, a process that never comes up.

The pin must carry the extra:

```
google-auth[requests]==2.56.*
```

Consequence, written down so nobody "tidies" it away: **this small backend now
runs two HTTP clients on purpose.** httpx is ours; `requests` belongs to
google-auth's transport. There is no supported httpx transport for
`verify_oauth2_token`.

## `TransportError` is not a `ValueError` — `except ValueError` is a hole

`id_token.verify_oauth2_token` raises `ValueError` for a token that is expired,
forged, or addressed to a different `aud`. It raises
**`google.auth.exceptions.TransportError`** when it cannot *fetch* Google's
signing certificates. The MRO is `TransportError → GoogleAuthError → Exception`:
it never touches `ValueError`, so a single `except ValueError` lets it straight
through as an unhandled **500**.

The version that looks like a fix is worse. Widen the except to cover both and a
user holding a perfectly valid token is told *"your sign-in has expired"* — signs
in again, gets the same message, forever, while nothing is wrong with their
sign-in at all.

**This is the same bug class as "A quota error is not an outage" above:** two
unrelated failures collapsed into one answer, which is then wrong for one of
them. Now caught separately — `401` for a bad token, `502` *"Could not reach
Google to verify your sign-in."* for a transport failure.

Proven, not assumed: constructing a transport that raises `TransportError` and
asserting on **which handler caught it**. A check that cannot fail is not a check.

## Verifying a token costs one outbound call to Google, every request

`verify_oauth2_token` fetches Google's certs on each call and google-auth does
**not** cache them. Against a 4–9s Gemini call it is noise. `/history` and
`/stories` are pure database reads, and they are measurably slower than before.

Documented, not fixed: caching the certs means owning their rotation, and that is
a real bug waiting when they roll.

## `use_fedcm_for_prompt` is deprecated and explicitly ignored by GIS

It was in the original spec for this work and was dropped after checking Google's
live reference. The current opt-in flag is **`use_fedcm_for_button`**.

Also under FedCM: `isDisplayMoment()`, `isDisplayed()`, `isNotDisplayed()` and
`getNotDisplayedReason()` are **unsupported**, and `getSkippedReason()` is
degraded. Do not add One Tap moment-listener logic without rechecking these
first — the handlers will simply never fire.

The general lesson, and the reason this is here rather than in a commit message:
**the GIS API surface is moving.** Check the live reference; do not write it from
memory.

## One Tap is a prompt, not a sign-in — and it looked like being asked twice

`google.accounts.id.prompt()` ran on every page load. Dismissing or ignoring the
One Tap card leaves you **signed out**, so the next page raised it again — read
by anyone using it as "why is it asking me to sign in a second time?". Next to
the always-rendered button it also put two ways to sign in on one screen.

One Tap is the fragile half of GIS: it needs FedCM, third-party cookie
permission, and no content blocker in the way. That is exactly why it worked on
some machines and silently did nothing on others. **The rendered button depends
on none of that.** `prompt()` is gone, and `auto_select` with it — that flag only
ever applied to One Tap, so keeping it would have been a no-op.

Sign-in also no longer appears on the hub at all. `index.html` calls exactly one
endpoint, `/healthz`, which is unauthenticated — so the bar there bought nothing
and cost a whole extra prompt. **Put sign-in where the authenticated call is.**

### The personalised button is one control, not a second prompt

With an active Google session, `renderButton` draws a **personalised** button —
the account's name and email inside the same iframe. It looks like a "sign in
as ..." card, which is easy to mistake for a One Tap overlay that never went
away. Settle it by measuring, not by looking:

```js
[...document.querySelectorAll('div')].filter(d => /credential_picker|onetap/i.test(d.id))  // [] = no overlay
document.getElementById('g-signin').querySelectorAll('iframe').length                      // 1 = one control
```

### Don't grep for a call in text that also documents it

Two checks disagreed with reality in opposite directions here. `grep "id.prompt()"`
matched the **comment** explaining why the call was removed, and the in-page
equivalent inherited the same flaw because `Function.prototype.toString()`
preserves comments. Strip comments before asserting:

```js
const src = fn.toString().replace(/\/\/[^\n]*/g, "").replace(/\/\*[\s\S]*?\*\//g, "");
/id\.prompt\s*\(/.test(src)   // the honest answer
```

Same family as the `AQ\.A`/`rnd_` scanner that flagged this very file: **match the
parsed thing, not text that happens to contain the words.**

## The Google account chooser cannot be driven by browser automation

Clicking the rendered button opens Google's chooser in a **separate window**,
outside the extension's tab group — three attempts, no popup reachable. So the
final click-through is the one step that has to be done by hand.

Everything either side of it *is* automatable, and worth doing rather than
skipping the test entirely: feed `handleGoogleCredential` a synthetic credential
to prove storage → UI flip → button enable, then let the backend reject it to
prove the 401 path clears the token, restores the button, and leaves the generate
button **disabled** rather than live and useless.

## Consumer OAuth client IDs cannot be listed from a terminal — at all

There is **no API and no gcloud command** that enumerates consumer OAuth 2.0
client IDs. They are console-only. Two commands look like they should work and
answer a different question:

| Command | What it actually covers | Result here |
|---|---|---|
| `gcloud iam oauth-clients list` | **Workforce Identity Federation** clients — a different product | `[]` |
| `gcloud alpha iap oauth-brands list` | **IAP** only, and deprecated (shutdown announced 19 Mar 2026) | not applicable |

So *"does an OAuth client already exist for this project?"* **cannot be settled
from a terminal.** Only <https://console.cloud.google.com/apis/credentials>
answers it.

Worth recording because a full disk-and-API sweep came back clean and looked
authoritative. It was answering a question nobody asked.

## Authorized JavaScript **origins**, not redirect URIs

The GIS ID-token flow never redirects, so the client has **no redirect URI at
all** — the field to fill in is *Authorized JavaScript origins*. Getting this
backwards produces a client that is configured, looks right, and fails at runtime
with `origin_mismatch`.

- **No trailing slash, no path.** `https://ai-app-bedtimestory.vercel.app` — not
  `.../` and not `.../story.html`.
- Local development needs its own entry: `http://localhost:5500`.
- **Changes take ~5 minutes to propagate.** A brand-new client that fails
  immediately is usually just not live yet. Wait before changing anything.

The contrast is worth holding onto: a server-side authorization-code flow is the
exact opposite shape — redirect URIs, and no JavaScript origins.

## The consent screen must be PUBLISHED, not left in Testing

Testing mode caps the app at **100 test users**, each of which has to be added by
hand. With only the non-sensitive scopes this app uses — `openid`, `email`,
`profile` — publishing costs nothing:

- no Google verification review
- no "unverified app" warning screen
- no user cap

There is therefore **no reason to stay in Testing**. Leaving it there is the
default, not a decision, and it fails for the 101st person with an error that
does not mention the cap.

## A stray gcloud `billing/quota_project` poisons calls for a different account

On this machine `billing/quota_project` was set to `ve-grp-1-444-project4-3fpi`
(an unrelated NTU project). Every call made as `--account=simoraj@gmail.com`
failed with **`USER_PROJECT_DENIED`** — the account is fine, the project it is
being billed against is not one that account may use.

`CLOUDSDK_BILLING_QUOTA_PROJECT=""` **does not clear it.** The working route was
to bypass gcloud's config entirely and call REST directly:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-access-token --account=simoraj@gmail.com)" ...
```

A gcloud config is machine-wide state that outlives whatever set it. When a
command fails for one account and works for another, check the config before the
permissions.

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

✅ **Resolved 8 Aug 2026 — the repo is linked and push-to-deploy works on both
halves.** Kept because the diagnosis is reusable and `repo_not_found` will lie
the same way next time.

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

It works and goes live in seconds, but **loses auto-deploy** — every frontend
change needs another manual upload. That was `scripts/deploy_frontend.py`, which
was deleted once the link went live. If you ever need it again, it is in the
history: `git show c0fc17d:scripts/deploy_frontend.py`.

### ⚠️ Linking does not deploy what is already pushed

Linking the repo subscribes Vercel to **future** push events. It does not build
the current commit. A commit pushed *before* the link existed never fired a
webhook, so the site keeps serving the old build with no error anywhere — the
dashboard says "Connected", the repo says up to date, and the two are describing
different things.

Hit exactly this on 8 Aug 2026: `c0fc17d` moved `escapeHtml` into `config.js`,
was pushed minutes before linking, and simply never deployed. Fix is one push —
an empty commit is enough, and it doubles as proof the webhook works:

```bash
git commit --allow-empty -m "Trigger first Vercel build" && git push
```

**Assert on the deployed bytes, not the dashboard badge:**

```bash
curl -s https://ai-app-bedtimestory.vercel.app/config.js | grep escapeHtml
```

The old build was internally consistent — old pages carried their own inline
`escapeHtml` — so nothing looked broken. A *partial* deploy would have been worse:
new HTML plus old `config.js` is a `ReferenceError` that kills history rendering.
Vercel deploys atomically, so that window does not exist, but it is the failure
mode to reason about whenever a page starts depending on a shared script.

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

# Reading the tracking data

**The admin panel is <https://ai-app-bedtimestory.vercel.app/admin.html>.** It is
deliberately not linked from the hub — bookmark it. Anyone else who finds the URL
gets a `403`, because the gate is `ADMIN_EMAIL` on the server, not the absence of
a link.

## Counting sign-ins: why `last_seen_at` was not enough

`users.last_seen_at` answers *"when was this person last here"*. It cannot answer
*"how many times"* or *"how many people were about on Tuesday"* — it is a single
column that gets **overwritten**. Those are questions about events, and a state
cannot answer them however often you update it.

Hence `sign_ins`. The trap in filling it is that the auth dependency runs on
**every authenticated request**, so writing a row there logs requests, not
sign-ins: opening the story page and generating once would look like several.

`token_iat` is the ID token's `iat` claim — fixed for the life of a token, and
different only when Google issues a new one, which is exactly what a sign-in is.
`UNIQUE (user_id, token_iat)` + `ON CONFLICT DO NOTHING` then does the counting,
so the call site never has to work out which of its requests is the first.

Proven rather than assumed: 50 inserts with one token produce **1** row; a new
token produces a 2nd.

## `generate_series`, not `GROUP BY`, for a daily chart

A day with no activity has **no rows to group**, so `GROUP BY day` silently omits
it and a 14-day chart draws a misleadingly continuous line over a quiet week.
Generate the days first and count into them:

```sql
WITH days AS (
  SELECT generate_series(current_date - interval '13 days', current_date, interval '1 day')::date AS day
)
SELECT d.day,
       (SELECT count(*) FROM sign_ins g WHERE g.created_at::date = d.day) AS sign_ins
FROM days d ORDER BY d.day;
```

The same instinct as *"silence is not success"*: an absent row and a zero look
identical in a chart, and only one of them is the truth.

## The queries

`/admin/usage` renders the headline numbers. These are the queries behind them,
for when you want the shape rather than the summary. Run them against the local
container, or against production through a temporarily opened `/32`.

```sql
-- Who has signed in, how often, and when they were last about.
SELECT u.email, u.name,
       count(g.id)                                        AS sign_ins,
       to_char(min(g.created_at), 'YYYY-MM-DD HH24:MI')   AS first_sign_in,
       to_char(u.last_seen_at,    'YYYY-MM-DD HH24:MI')   AS last_seen
FROM users u LEFT JOIN sign_ins g ON g.user_id = u.id
GROUP BY u.id, u.email, u.name, u.last_seen_at
ORDER BY sign_ins DESC;

-- Sign-ins per day, quiet days included.
SELECT d.day, count(g.id) AS sign_ins
FROM (SELECT generate_series(current_date - interval '29 days', current_date, interval '1 day')::date AS day) d
LEFT JOIN sign_ins g ON g.created_at::date = d.day
GROUP BY d.day ORDER BY d.day;

-- Came back, or signed in once and never returned?
SELECT count(*) FILTER (WHERE n = 1) AS one_and_done,
       count(*) FILTER (WHERE n > 1) AS returned
FROM (SELECT user_id, count(*) AS n FROM sign_ins GROUP BY user_id) s;
```

```sql
-- 1. Signups over time. One row per person, ever.
SELECT date(created_at) AS day, count(*) AS signups
FROM users GROUP BY day ORDER BY day;

-- 2. What each person has actually made.
SELECT u.email,
       (SELECT count(*) FROM stories      s WHERE s.user_id = u.id) AS stories,
       (SELECT count(*) FROM interactions i WHERE i.user_id = u.id) AS questions,
       u.created_at, u.last_seen_at
FROM users u ORDER BY stories DESC, questions DESC;

-- 3. Most active in the last 7 days - who is actually still using it.
SELECT u.email, count(*) AS stories
FROM stories s JOIN users u ON u.id = s.user_id
WHERE s.created_at > NOW() - INTERVAL '7 days'
GROUP BY u.email ORDER BY stories DESC;

-- 4. Daily actives across BOTH apps. Distinct people, not rows: three stories
--    in one night is one active person, not three.
SELECT day, count(DISTINCT user_id) AS people FROM (
    SELECT date(created_at) AS day, user_id FROM stories
    UNION ALL
    SELECT date(created_at),        user_id FROM interactions
) a WHERE user_id IS NOT NULL GROUP BY day ORDER BY day;

-- 5. Rows that predate sign-in. These never get an owner - the number should
--    stay frozen forever. If it grows, a route is writing without a user_id.
SELECT (SELECT count(*) FROM stories      WHERE user_id IS NULL) AS stories,
       (SELECT count(*) FROM interactions WHERE user_id IS NULL) AS questions;
```

Two caveats to read them honestly:

- **`last_seen_at` means "last authenticated request", not "last signed in".**
  The upsert in `current_user` runs on every call, so simply opening a page with
  a live token bumps it.
- **A row is created on first sign-in, not on first use.** Query 1 counts people
  who arrived; query 2's zeroes are the ones who arrived and did nothing.

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

# the preflight must now ALLOW the Authorization header, or the browser never
# sends the real request - "Failed to fetch", nothing in the backend log
curl -i -X OPTIONS http://localhost:8000/story -H "Origin: http://localhost:5500" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Authorization"   # 200, Authorization listed

# auth - every one of these must be 401 with no token
curl -i http://localhost:8000/history                  # 401
curl -i http://localhost:8000/stories                  # 401
curl -i http://localhost:8000/admin/usage              # 401
curl -i -X POST http://localhost:8000/story -H "Content-Type: application/json" \
  -d '{"child_name":"A","theme":"b"}'                  # 401 BEFORE Gemini is called

# data
docker exec ai-apps-pg psql -U postgres -d ai_apps \
  -c "SELECT id, question, created_at FROM interactions ORDER BY id DESC;"
```

The `POST` cases matter for a reason beyond access control: the dependency runs
**before** the handler, so unauthenticated traffic never reaches `call_gemini`
and burns **no free-tier quota**. Check the ordering, not just the status code —
a 401 returned after the model call would look identical from outside.

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

**Closed since:**

1. ✅ **Vercel ↔ GitHub link** — `git push` now deploys both halves; first
   webhook build reached the CDN in ~40s. `scripts/deploy_frontend.py` deleted
   with it, since it existed only to cover the missing link.
2. ✅ **Both deploy tokens rotated** — everything exposed earlier in the session
   is dead, and nothing in the repo reads either token now.
3. ✅ **Google sign-in, and the history leak it closed** (below).

## Sign-in — added 8 Aug 2026

**Production database migrated**: `users` created, nullable `user_id` added to
both tables, `(user_id, id DESC)` indexed on both. `ipAllowList` was opened to a
single `/32` for the migration and closed again — and *verified* closed by
attempting a real connection afterwards and being refused, not by reading the
API's response to the PATCH.

Verified locally, and this is the record to re-run after any change to
`auth_service.py` or the CORS config:

| Check | Result |
|---|---|
| `GET /stories`, `GET /history` with no token | **401** (was 200 + every user's data) |
| `POST /story`, `POST /ask` with no token | **401 before Gemini is called** — unauthenticated traffic burns no quota |
| Preflight carrying `Access-Control-Request-Headers: Authorization` | **400 → 200**, with `Authorization` in `access-control-allow-headers` |
| Rogue-origin preflight | still **400**, no allow-origin — unchanged by any of this |
| Two users, two tokens, same endpoints | **no cross-user leakage** in either app |
| `/admin/usage` | SQL verified by calling `fetch_usage()` directly — the route is behind a token that cannot be minted locally |

## Outstanding

1. **2026-09-07** — free Postgres expires; `/healthz` will show `postgres: false`.
   **This is now worse than it was.** Before sign-in it cost the story log; now
   the `users` table dies with it, so every account goes too. Everyone signs in
   again into an empty history, and there is no export. This is the top risk in
   the project and it has a fixed date.
2. **`GOOGLE_CLIENT_ID` in `frontend/config.js` is still the placeholder**
   (`REPLACE_WITH_CLIENT_ID.apps.googleusercontent.com`). Until the real value is
   pasted in and pushed, the deployed frontend cannot sign anyone in — and the
   failure is at Google's end, so the backend log stays empty. Assert on the
   deployed bytes, not on the file you edited:

   ```bash
   curl -s https://ai-app-bedtimestory.vercel.app/config.js | grep GOOGLE_CLIENT_ID
   ```
