# AI Apps

Two **single-turn** AI apps behind a hub page — a FastAPI backend on Render, a
static frontend on Vercel, Gemini for the model, Postgres for the record.

| # | App | Page | What it does |
|---|---|---|---|
| 1 | 💬 Chat | `chat.html` | Ask a question, get a short answer. Every exchange is saved. |
| 2 | 🌙 Bedtime Story | `story.html` | A gentle ~200-word story built around a child's name and a theme. |
| 📖 | Your story stats | `mystats.html` | Your own totals — words, read-aloud time, reading level, who each story was for. |
| 📊 | Usage | `admin.html` | Owner-only: who signed in, how often, and what they made. Not linked from the hub. |

**Single-turn** means one request in, one answer out. The model never sees
earlier exchanges — the saved history is for *you* to read back, not context fed
into the prompt.

**Sign in with Google to use either app.** Your stories and questions are yours;
nobody else can read them. Pages still load signed out — the button is just
disabled until you sign in.

Sign-in appears on the two app pages only, not on the hub. The hub carries a
short *How it works* instead.

## 🚀 Live

| | |
|---|---|
| **App** | <https://ai-app-bedtimestory.vercel.app> |
| **API** | <https://ai-app-bedtimestory.onrender.com> |
| Health | <https://ai-app-bedtimestory.onrender.com/healthz> |
| Your story stats | <https://ai-app-bedtimestory.vercel.app/mystats.html> |
| Usage (owner only) | <https://ai-app-bedtimestory.vercel.app/admin.html> |

`git push origin master` deploys both halves — Render rebuilds the backend,
Vercel rebuilds the frontend.

The backend sleeps after 15 minutes idle, so the first request after a quiet
spell takes 30–60s. The pages themselves load instantly from the CDN.

## Architecture

```
                        ┌──► Google: sign in, get an ID token (JWT)
                        │
Browser ──(static files)┴─► Vercel:  frontend/
   │
   └──(fetch, cross-origin, Authorization: Bearer <jwt>)──► Render:  FastAPI
                                  ├──httpx───────► Gemini API
                                  ├──google-auth─► Google certs (verify the JWT)
                                  └──psycopg────► Postgres (one DB, three tables)
```

The frontend and backend are **separate deployments on separate origins**, which
is why CORS matters here. `frontend/config.js` derives the backend URL from the
hostname, so there is nothing to edit when moving between local and production.

Those two origins are also why sign-in uses a **Google ID token rather than a
session cookie**: `vercel.app` and `onrender.com` are different registrable
domains, so no cookie can span them — it would be a third-party cookie, which
Safari blocks. There is no client secret, no redirect URI and no callback route;
the browser is handed a signed token and the backend checks the signature.

```
app/                       backend - API only, no HTML
  main.py                  CORS + routes + /healthz
  database.py              DATABASE_URL + get_conn()
  schemas.py               chat models, story models, CurrentUser, usage models
  services/
    gemini_service.py      the only file that talks to Gemini
    auth_service.py        the only file that talks to Google identity
    text_stats.py          stdlib only - counts, Flesch scores, genre lexicon
    chat_service.py        save_interaction / fetch_recent_history
    story_service.py       save_story / fetch_recent_stories / fetch_my_stats
    admin_service.py       fetch_usage - totals, per-person counts, 14-day series, genres, recent feed
frontend/                  frontend - static, deploys to Vercel
  index.html               hub - no sign-in, three cards + How it works
  chat.html  story.html    the two apps - sign-in lives here
  mystats.html             the reader's own totals and charts
  admin.html               owner-only usage, not linked from the hub
  config.js                BACKEND_URL + escapeHtml + sign-in + readingBand/readingTime
  style.css
sql/001_create_interactions.sql
sql/002_create_stories.sql
sql/003_create_users.sql       one row per Google account, keyed on google_sub
sql/004_add_user_id.sql        nullable user_id on both tables + indexes
sql/005_create_sign_ins.sql    one row per actual sign-in, deduped on token_iat
sql/006_add_story_stats.sql    nullable word/sentence/level/genre columns on stories
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
| Sign-in | google-auth `[requests]` | `2.56.*` | Verifies the Google ID token on every authenticated request. **The `[requests]` extra is required, not optional** — `google.auth.transport.requests` imports `requests`, and without it the backend fails at *import*. That is why this backend has two HTTP clients: httpx is ours, `requests` is google-auth's transport. |
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
docker exec -i ai-apps-pg psql -U postgres -d ai_apps < sql/003_create_users.sql
docker exec -i ai-apps-pg psql -U postgres -d ai_apps < sql/004_add_user_id.sql
docker exec -i ai-apps-pg psql -U postgres -d ai_apps < sql/005_create_sign_ins.sql
```

In order — `004` and `005` both add foreign keys to `users`, so `003` has to
exist first.

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

# and the routes that must never answer without a token
curl -i http://localhost:8000/stories  # 401
curl -i http://localhost:8000/history  # 401
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
timestamp, and since sign-in a `user_id`. Nothing links one row to the *next*.
That's the single-turn design: a log of exchanges, not a conversation transcript.

Rows written before sign-in existed have `user_id IS NULL` and always will —
they show up as *"(before sign-in)"* on the usage page rather than being dropped.

Data survives `docker stop`/`start`; lost only on `docker rm`.

## Analytics

Two views. Both need a signed-in caller; each shows only what that caller is
entitled to see.

**Your story stats** — `mystats.html`. Reached from a card on the hub and from a
chip in the story page's auth bar. Anyone signed in gets their own numbers, and
only their own — every query filters on the `user_id` from the verified token
and takes no parameter that could widen it.

| | |
|---|---|
| Tiles | stories · words · words each |
| Story length | column chart, one per story, oldest first — with a collapsed table twin so no value needs a hover |
| Reading level | meter, the average against an easier→harder scale |
| Who they were for | horizontal bars per child |
| What they were about | horizontal bars per genre |

Charts are hand-written inline SVG — no chart library, no build step. One mark
colour throughout, because genre and child names are nominal: colouring each bar
separately would re-encode what bar length already shows. Design notes and the
measured contrast figures are in `CLAUDE.md` → *Charts*.

**Usage** — `admin.html`, restricted to `ADMIN_EMAIL`. Not linked from the hub.
The owner reaches it from a link on their own stats page, shown only when the
server sets `is_admin` on `/me/stats` — the browser never decides this for itself,
because it can decode a token but not verify one. Anyone else who finds the URL
gets `403`.

| | |
|---|---|
| Tiles | people · sign-ins · stories · questions |
| Last 14 days | per day: distinct people, sign-ins, stories, questions |
| People | per person: sign-ins, stories, questions, joined, last seen |
| Story genres | per genre: stories, average words, reading level |
| Recent activity | the last 20 actions across both apps |

Sign-ins are counted from the `sign_ins` table rather than `users.last_seen_at`,
which is overwritten on every request and so cannot answer "how many times".
Rows are deduped on the ID token's `iat` claim, so a token reused across many
requests counts once. SQL for both views is in `CLAUDE.md` → *Reading the
tracking data*.

## API

| Method | Route | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | — | JSON banner — confirms the API is up |
| `POST` | `/ask` | 🔐 | `{question}` → `{answer, history[]}` |
| `GET` | `/history` | 🔐 | Your 10 most recent exchanges |
| `POST` | `/story` | 🔐 | `{child_name, theme, length?}` → `{story, history[]}`. `length` is `short` \| `medium` \| `long`, defaulting to `medium`. |
| `GET` | `/stories` | 🔐 | Your 10 most recent stories |
| `GET` | `/me/stats` | 🔐 | Your own totals across every story you have made — words, read-aloud time, reading level, who each was for, what they were about |
| `GET` | `/admin/usage` | 🔐 owner | Totals, per-person counts, a 14-day daily series, and the 20 most recent actions |
| `GET` | `/healthz` | — | `{"gemini": bool, "postgres": bool}` — always 200; a diagnostic, not a gate |

🔐 means `Authorization: Bearer <google-id-token>`. History is **per user** — the
`user_id` comes from the verified token, never from the request body.

Errors: `400` blank input or unknown length · `401` missing, expired or invalid
token · `403` signed in but not `ADMIN_EMAIL` · `422` malformed body (Pydantic) ·
`429` free-tier quota exceeded · `502` Gemini, Postgres, **or Google's certs
endpoint** unreachable.

`401` and `502` are kept apart deliberately: *"your sign-in has expired"* is
useless advice to someone holding a valid token whose verification simply could
not reach Google.

The `401` is raised **before** the model is called, so unauthenticated traffic
costs no Gemini quota.

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
| `GOOGLE_CLIENT_ID` | The OAuth 2.0 **Web application** client ID — see below |
| `ADMIN_EMAIL` | The one Google address allowed to read `/admin/usage` |

Read with `os.environ["..."]` at import time, so a missing one is a loud
`KeyError` at startup rather than a confusing failure later.

On Render, `GOOGLE_CLIENT_ID` and `ADMIN_EMAIL` are `sync: false` in
`render.yaml` — set them in the dashboard. Neither is a secret the way
`GEMINI_API_KEY` is: the client ID is **public by design** (it ships in
`frontend/config.js` too), and `ADMIN_EMAIL` is a personal address kept out of
git, not a credential. Knowing it grants nothing — you still need a Google token
proving you own it.

### Creating the OAuth client

There is **no API and no gcloud command** that lists or creates a consumer OAuth
client. It is console-only, so this is by hand, once:

1. <https://console.cloud.google.com/apis/credentials> — pick the project, and
   **check which Google account the browser is signed in as.** Creating the
   client under one account and then signing into the app with another is the
   easy mistake here: everything works except `/admin/usage`, which 403s.
2. **OAuth consent screen** → scopes `openid`, `email`, `profile` → **Publish**.
   Leaving it in *Testing* caps the app at 100 hand-added test users. At these
   scopes publishing needs no Google review and shows no "unverified app"
   warning, so there is no reason to stay in Testing.
3. **Create credentials → OAuth client ID → Web application.**
4. **Authorized JavaScript origins** — *not* redirect URIs. This flow never
   redirects and has no redirect URI at all:
   - `http://localhost:5500`
   - `https://your-project.vercel.app`

   No trailing slash, no path, or you get `origin_mismatch` at runtime.
   Changes take about **5 minutes to propagate** — a brand-new client that fails
   straight away is usually just not live yet.
5. Copy the client ID into **three** places: `.env`, the Render dashboard, and
   `GOOGLE_CLIENT_ID` in `frontend/config.js`. A stale value there rejects every
   sign-in silently, because it is what the token's `aud` claim is checked
   against.

A fresh checkout ships a placeholder
(`REPLACE_WITH_CLIENT_ID.apps.googleusercontent.com`) in `frontend/config.js`;
this repo's copy holds the real ID. Either way, check the **deployed** file
rather than the one you edited — a wrong client ID fails at Google's end, so
nothing appears in the backend log at all:

```bash
curl -s https://ai-app-bedtimestory.vercel.app/config.js | grep GOOGLE_CLIENT_ID
```

### One sign-in affordance

`config.js` does **not** call `google.accounts.id.prompt()`, and has no
`auto_select`. One Tap is a prompt rather than a sign-in, so dismissing it left
people signed out and it reappeared on the next page — and it depends on FedCM,
third-party cookies and no content blocker, so it worked on some machines and
silently did nothing on others. The rendered button is the only way in. Reasoning
in full: `CLAUDE.md` → *One Tap is a prompt, not a sign-in*.

With an active Google session that button renders **personalised**, showing the
account name inside its iframe. It looks like a "sign in as…" card but is one
control, not a leftover overlay.

`frontend/config.js` — `BACKEND_URL` is auto-detected from the hostname, so
there is nothing to edit per environment. It also holds `GOOGLE_CLIENT_ID` and
the sign-in client. **Never put a key in `frontend/`** — every visitor can read
it. The client ID is not a key: this flow has no client secret, which is why it
suits a static frontend.

`.render.env` and `.vercel.env` — **tooling only**. They hold account-wide
control-plane keys, are gitignored, and must never be deployed. Both tokens were
rotated on 8 Aug 2026, so anything exposed earlier is dead.

Nothing in the repo reads them any more: both hosts deploy from Git, and
`deploy_frontend.py` — the only consumer `VERCEL_TOKEN` ever had — was deleted
once the Vercel link went live. Keep the files only if you use the APIs by hand;
otherwise revoking both leaves nothing to leak.

## Deploying

Both halves deploy on push ✅

```bash
git push origin master   # Render rebuilds the backend, Vercel rebuilds frontend/
```

Render reads `render.yaml` and `Procfile`; Vercel reads `vercel.json`, whose
`outputDirectory: "frontend"` is what makes a Git build publish `frontend/` at
the site root. Verified 8 Aug 2026: a push reached the CDN in about 40 seconds.

### If the Vercel link ever breaks

Linking is **two separate steps**, and doing only the first is the usual cause of
"connected, but pushes do nothing":

1. <https://github.com/settings/installations> → **Vercel** → **Configure** →
   *Repository access* → add `ai-app-bedtimestory` → **Save**
2. Vercel → Project → **Settings → Git** → connect the repository

Making the repo public will **not** substitute for this — Vercel needs the
GitHub App for webhooks, and the webhook is what turns a push into a deploy.

Linking subscribes to **future** pushes; it does not build the current commit.
After linking, the site keeps serving the previous build until the next push, so
verify against the deployed bytes rather than the dashboard badge:

```bash
curl -s https://ai-app-bedtimestory.vercel.app/config.js | grep escapeHtml
```

### If you ever rebuild from scratch

⚠️ **Circular dependency.** The frontend needs the backend's URL; the backend's
CORS needs the frontend's URL. Neither exists first, so it takes two passes:

1. **Render** — create the service + Postgres, set `GEMINI_API_KEY`, apply all
   five migrations in order. Note the backend URL.
2. Set `BACKEND_URL` in `frontend/config.js`, commit, push.
3. **Vercel** — deploy. Read the production alias from the response; don't assume
   it.
4. Set `FRONTEND_ORIGINS` on Render to that alias. Redeploy.
5. Create the OAuth client (above) with that alias as an **authorized JavaScript
   origin**, then set `GOOGLE_CLIENT_ID` and `ADMIN_EMAIL` on Render and put the
   client ID in `frontend/config.js`.

Sign-in joins the circular dependency rather than escaping it: the OAuth client
needs the Vercel origin, which does not exist until step 3.

Render's Postgres refuses external connections by default (`ipAllowList: []`),
and reports it as `SSL connection has been closed unexpectedly`. To run
migrations: add your IP as a `/32`, migrate, remove it. See `CLAUDE.md`.

A free Render Postgres expires 30 days after it is created, so don't create it
before you intend to deploy. `GET /v1/postgres/<id>` reports the plan and any
`expiresAt` if you need to check.

## Known limits

Honest edges of a single-turn, ungrounded app — not bugs:

- **No memory.** The same question twice gives the same answer; the model doesn't
  know it just replied.
- **No grounding.** Asked "who won the world cup" in August 2026, it named the
  2022 tournament. Its training data ends earlier and nothing supplies current
  facts.
- **No clarifying questions.** Ambiguous prompts get hedged answers covering every
  interpretation, because there's no next turn in which to ask.
- **No walk-up use.** Sign-in is required to generate anything. That was a real
  property of the earlier version and it is gone — the trade is recorded in
  `PRD.md` §5.1.
- **Verification costs a round trip.** Every authenticated request makes one
  outbound call to Google's certs endpoint; google-auth doesn't cache them.
  Invisible next to a Gemini call, measurable on `/history`.

## Tuning the output

`CHAT_SYSTEM_PROMPT` and `STORY_SYSTEM_PROMPT` in
`app/services/gemini_service.py` shape the output far more than any code change.
Predict what an edit will do *before* running it, then compare — that gap is
where the learning is.

## Adding a third app

1. A system prompt constant in `gemini_service.py`
2. A `<name>_service.py` with save + fetch, both taking a `user_id`
3. Schemas in `schemas.py`
4. A page in `frontend/`, and a card on the hub in `frontend/index.html`
5. A `sql/00N_create_<name>.sql`, with a nullable `user_id REFERENCES users(id)`
   and a `(user_id, id DESC)` index
6. Routes in `main.py`, each taking `user: CurrentUser = Depends(current_user)`

Skip steps 2, 5 or 6's dependency and the new app is the one that leaks
everyone's data — which is exactly what `/stories` did before sign-in existed.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to fetch` in the browser, **nothing in the backend log** | CORS blocked the preflight — the request never arrived | Check `FRONTEND_ORIGINS` matches the frontend origin exactly, scheme and port included |
| New routes 404, edits do nothing, **no access-log lines** | A stale uvicorn worker is still serving | See `CLAUDE.md` → orphaned workers. Check reality with `curl localhost:8000/openapi.json` |
| `KeyError: 'GEMINI_API_KEY'` | No `.env` in the project root | `cp .env.example .env` and fill it in |
| `ModuleNotFoundError: No module named 'requests'` at startup | `google-auth` installed without its extra | The pin must be `google-auth[requests]`. Re-run `pip install -r requirements.txt` |
| Every sign-in fails, `401`, nothing obviously wrong | `GOOGLE_CLIENT_ID` doesn't match the token's `aud` | It must be identical in `.env`, Render, **and** `frontend/config.js` |
| `origin_mismatch` when the Google button is clicked | The page's origin isn't authorized on the OAuth client | Add it as an **authorized JavaScript origin** — no trailing slash, no path. Allow ~5 min to propagate |
| Signed in fine, `/admin/usage` says "for the app owner only" | Signed in as a different Google account than `ADMIN_EMAIL` | Check which Chrome profile the browser used, then sign out and back in |
| The Google button never appears | `accounts.google.com` blocked by a content blocker or network | The page says so where the button would be — there's no fallback |
| The Google button renders as a bare "G" icon | Its container has no width basis, so Google's iframe collapses | `#g-signin` needs a `min-width`. `renderButton`'s `width` option is a hint the iframe can't honour when the flex item has no size |
| Looks like a second sign-in prompt on every page | One Tap (`prompt()`) was reintroduced, or you're seeing the personalised button | Check for a real call, not comment text: `grep` matches the comment explaining its removal, and `Function.toString()` preserves comments. Strip them first |
| `/healthz` shows `postgres: false` | Container not running | `docker start ai-apps-pg` |
| Request hangs ~10s then 502 | Postgres unreachable; Windows blackholes the closed port | Start the container. `connect_timeout=5` makes this fail in seconds, not forever |
| `ModuleNotFoundError: No module named 'app'` | Ran a script by path | `python -m scripts.smoke_gemini` from the project root |
| Frontend server won't start on 3000 | Docker Desktop holds that port | Use 5500 |
| Render/Vercel API returns bare `401` | Truncated token paste | Render ~32–40 chars, Vercel 60 |

## More

- `CLAUDE.md` — conventions, insights, and the full gotcha list
- `PRD.md` — scope, open decisions, milestones, risks
