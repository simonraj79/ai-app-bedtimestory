# PRD — AI Apps

**Status:** ✅ **V1 shipped — live in production** · **Last updated:** 8 August 2026
**Owner:** Simon · **Related:** `CLAUDE.md` (conventions, insights, gotchas), `README.md` (how to run)

| | URL |
|---|---|
| **Frontend** | <https://ai-app-bedtimestory.vercel.app> |
| **Backend** | <https://ai-app-bedtimestory.onrender.com> |

⚠️ Free Postgres **expires 2026-09-07** — and since 8 Aug 2026 the `users` table
lives there too, so **accounts die with it**. ✅ Auto-deploy wired on both halves —
`git push` redeploys backend and frontend. 🔐 **Google sign-in is required to
generate**; history is per-user.

---

## 1. What this is

A small family of **single-turn** AI apps behind a hub page. App 1 is the Single
Turn Chat — the foundation. App 2 is the Bedtime Story Generator: the same
architecture pointed at a narrower job.

| # | App | Page | Endpoint | Table | Status |
|---|---|---|---|---|---|
| 1 | 💬 Chat | `chat.html` | `POST /ask` | `interactions` | ✅ **Live** |
| 2 | 🌙 Bedtime Story | `story.html` | `POST /story` | `stories` | ✅ **Live** |
| — | 📊 Usage (owner only) | `admin.html` | `GET /admin/usage` | `users` + both | ✅ **Live** 8 Aug 2026 |

Since 8 Aug 2026 both apps require **Google sign-in**, and each person sees only
their own history. `GET /` and `GET /healthz` are the only open routes.

## 2. Problem

- **Chat** — a personal, private question box with a permanent record you own.
  Public chatbots keep no log you control.
- **Bedtime Story** — a parent wants a story *about their child*, without
  inventing one while exhausted. Story books don't personalise.

## 3. Goal

One input, one useful answer, in under ten seconds, saved so it can be found
again.

**Success looks like:** used twice in the same week without being prompted.

## 4. Users

| User | Need |
|---|---|
| Simon (operator) | ~~Fast, private, no login friction.~~ A record he owns, **and to know who else is using it.** |
| Any signed-in person | Their own stories and questions, visible to nobody else. |
| Child (audience, app 2) | A story with their name in it, that isn't frightening. |

~~Assumed a **single household**, no accounts.~~ **Superseded 8 Aug 2026** — see
§5.1.

## 5. Scope

### V1 — built ✅

- Static hub listing the apps
- **App 1 Chat:** question → short answer (under 80 words) → saved → 10 most
  recent listed
- **App 2 Bedtime Story:** child's name + theme → ~200-word gentle story, simple
  vocabulary, nothing frightening, ends with the child asleep → saved → listed
- `/healthz` reporting Gemini and Postgres separately
- Loud startup failure on missing configuration
- CORS restricted to declared origins, verified allowed *and* denied
- Deploy configs for both hosts, start command verified

### Explicitly out of scope for V1

| Not doing | Why |
|---|---|
| Conversation / "continue the story" | Makes it multi-turn: session keys, growing token cost, per-user isolation. |
| Grounding / web search | Would fix stale answers (§11) but is a distinct feature with its own failure modes. |
| ~~Accounts and login~~ | ~~Large, unrelated to the product, wrong for a bedtime device.~~ **Reversed 8 Aug 2026 — see §5.1.** |
| Streaming tokens | 2–8s is tolerable. Adds real complexity. |
| Illustrations, narration, PDF | See §8 — decided, not overlooked. |
| Tests | Not in V1, per the course doctrine this inherits. |

### 5.1 The goal changed — accounts are now in scope

**What changed, in one sentence:** the app stopped being a single-household tool
and became one whose operator wants to know *who* uses it and *what they do*.
That question is unanswerable without identity, so "no accounts" had to go.

Shipped 8 Aug 2026: Google sign-in (ID-token flow), per-user history, a `users`
table, and an owner-only `/admin/usage` page.

**What it cost — stated plainly, because the original entry was right about it:**

| Lost | Detail |
|---|---|
| **Walk-up use** | The app is no longer usable by someone who just opens the page. A tap on the Google button now stands between a tired parent and a story. This was a real property of V1 and it is gone. |
| **Zero-dependency start** | Sign-in needs `accounts.google.com` to load. Content blockers and some networks break it; `config.js` says so rather than leaving a dead button, but it is a failure mode V1 did not have. |
| **A second control plane** | A Google Cloud project, an OAuth client, and a consent screen now have to exist and stay correct. See `CLAUDE.md` — none of it can even be *listed* from a terminal. |
| **Latency on reads** | Every authenticated request costs one outbound call to Google's certs endpoint. Noise against Gemini; visible on `/history`. |

**What it bought, beyond the tracking:** it closed a real leak. Before this
change, `curl https://ai-app-bedtimestory.onrender.com/stories` — no token, no
`Origin` header — returned **200 and 3,099 bytes** of every child's name, theme
and full story. Verified, not theorised. The §12 "open API abuse" risk and the
§11 "CORS is not authentication" limit were describing this exact hole.

The mitigation for the cost is deliberate and thin: pages **render signed out**
with the submit button disabled and a one-line hint. A hidden form would have
been less code and reads as a broken app.

## 6. Design

### 6.1 Single-turn, deliberately

Each request sends exactly `[systemInstruction, one user message]`. The tables
are a **library for the human**, never context for the prompt.

**Confirmed observationally:** rows 2 and 3 of `interactions` are the same
question asked twice, with near-identical answers.

Descends from the course app (`fastapi-ollama-postgres-cohort`,
`module5-readiness-checklist.md:253`: *"Both courses build a single-turn LLM app —
one question in, one answer out"*), with two swaps: Gemini replaces Ollama, and
the cloud replaces localhost.

### 6.2 Split deploy — matching the course

Backend (FastAPI) on Render; frontend (static) on Vercel. Chosen deliberately in
preference to a single-origin deploy, to match the cohort's Module 7 architecture.

**What it costs:** CORS middleware, a `BACKEND_URL` constant, two deploys per
change, two dashboards, and a circular URL dependency at first deploy. These are
precisely the failure modes the course documents as its biggest source of student
pain (`setup_walkthrough.md:610`).

**What it buys:** the frontend is on a CDN with no cold start, the backend can
sleep without the page dying, and the lesson the course is actually teaching.

### 6.3 The system prompts are the product

`CHAT_SYSTEM_PROMPT` and `STORY_SYSTEM_PROMPT` carry length, tone, vocabulary,
safety and shape — more work than any code in the repo. Child safety for app 2
lives entirely in its prompt.

### 6.4 Layered so the provider is swappable

`main.py` knows only `call_gemini(question)` and
`generate_story(child_name, theme)`; both funnel through one `ask_gemini()`.
Moving from Ollama to Gemini touched exactly one file. Preserve this.

### 6.5 Data model

```sql
CREATE TABLE interactions (            CREATE TABLE stories (
    id          SERIAL PRIMARY KEY,        id          SERIAL PRIMARY KEY,
    question    TEXT NOT NULL,             child_name  TEXT NOT NULL,
    answer      TEXT NOT NULL,             theme       TEXT NOT NULL,
    model_name  TEXT NOT NULL,             story       TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()  model_name  TEXT NOT NULL,
);                                         created_at  TIMESTAMPTZ DEFAULT NOW()
                                       );
```

`model_name` per row on purpose: when the model changes you can tell which rows
came from which, and whether quality moved.

Since 8 Aug 2026, a third table and one column on each of the other two:

```sql
CREATE TABLE users (                    ALTER TABLE interactions
    id           SERIAL PRIMARY KEY,      ADD COLUMN user_id INTEGER
    google_sub   TEXT NOT NULL UNIQUE,    REFERENCES users(id);
    email        TEXT NOT NULL,
    name         TEXT NOT NULL,         ALTER TABLE stories
    picture      TEXT,                    ADD COLUMN user_id INTEGER
    created_at   TIMESTAMPTZ DEFAULT NOW(),  REFERENCES users(id);
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
);                                      -- + (user_id, id DESC) on both
```

Three decisions worth keeping:

- **Keyed on `google_sub`, not email.** The `sub` claim is stable for the life of
  the account; an email can be changed by its owner. Keyed on email, a rename
  forks one person into two rows and splits their history between them.
- **`user_id` is NULLABLE.** The 3 stories and 3 interactions already in
  production predate sign-in. `NOT NULL` would need a fabricated owner — a lie in
  the data. `NULL` means *"before sign-in"*, and `/admin/usage` labels those rows
  that way rather than dropping them, so totals and feed agree.
- **No events or analytics table.** `stories` and `interactions` already record
  what people do, with timestamps, and `users.last_seen_at` is maintained by the
  same upsert that authenticates — so return visits come for free. A fourth table
  would duplicate rows that already exist in order to count them. The queries are
  in `CLAUDE.md` → *Reading the tracking data*.

### 6.6 Sign-in is an ID token, not a session

Google Identity Services hands the browser a signed JWT; the browser sends it as
`Authorization: Bearer <jwt>`; the backend verifies the signature against
Google's public keys. **No client secret, no redirect URI, no callback route, no
cookie, no session store.**

That is not a simplification — §6.2's split deploy ruled out the alternatives:

- **A session cookie is impossible here.** `vercel.app` and `onrender.com` are
  different registrable domains, both on the Public Suffix List, so no cookie can
  span them. It would be a third-party cookie, which Safari blocks outright — the
  app would work in Chrome and fail silently on the device most likely to be used
  at bedtime.
- **The authorization-code flow needs a client secret** and a server-side
  callback. The secret cannot live in `frontend/`, which every visitor can read.

`GOOGLE_CLIENT_ID` therefore ships in `frontend/config.js` and is **public by
design**. The V1 invariant — *nothing secret in `frontend/`* — survives sign-in
untouched, because this flow has no secret to place there.

Full reasoning, and the gotchas it cost, in `CLAUDE.md`.

## 7. Non-functional

| Requirement | Target | Actual |
|---|---|---|
| Chat latency | < 5s | ~2.5s local · **4.0s in production** |
| Free-tier headroom | comfortable | **~500 req/day** on `gemini-3.5-flash-lite` |
| Story latency | < 15s | ~6–8s local · ~9s in production |
| Story length | 150–250 words | short ~96 · medium ~201 · long ~234 |
| Child-safe output | Always | Enforced by system prompt |
| Cost | Negligible | Free tier; hidden thinking tokens dominate |
| Config failure | Loud, at startup | `KeyError` on missing env var |
| Health check | Never hangs | `connect_timeout=5` on the DB probe |
| Cross-origin access | Declared origins only | Verified: allowed → 200, other → 400 |
| Authenticated access | Every generating route | Verified: no token → **401** on `/ask` `/history` `/story` `/stories` `/admin/usage` |
| Unauthenticated quota burn | None | The dependency runs **before** the handler, so a 401 costs no Gemini call |
| Per-user isolation | No cross-user reads | Verified with two users and two tokens: no leakage in either app |
| Admin access | One address | `403` for any signed-in caller who is not `ADMIN_EMAIL` |
| Auth overhead | Acceptable | One outbound call to Google's certs per request — noise vs Gemini, visible on `/history` |
| Secrets in repo | Zero | Verified with `git check-ignore` and a shape-based key scan. The OAuth client ID is public by design and is not one. |

## 8. Open decisions

V1 assumes the middle column and works today.

| # | Decision | V1 assumption | Alternatives |
|---|---|---|---|
| 1 | **Output modality (app 2)** | Text only | **Narration** (`gemini-3.1-flash-tts-preview`) — arguably the real killer feature for bedtime. Adds audio storage; Render's free disk is ephemeral, so stream or store bytes in Postgres. **Illustrations** (`imagen-4.0-fast-generate-001`, `nano-banana-pro-preview`) — high delight, slowest and priciest, needs its own child-safety pass since images don't inherit the prompt. **PDF keepsake** — no AI cost, pure templating. |
| 2 | **Child profiles (app 2)** | None — typed each time | Store name, age, favourite characters once and feed them into the system prompt. Where personalisation stops being a gimmick. Small change: a `children` table + FK. Best value-per-effort addition. |
| 3 | **Merge both apps into one project** | — | ✅ **Resolved 8 Aug 2026** — merged. |
| 4 | **Grounding for app 1** | Ungrounded | Model knowledge ends before 2026 and it answers stale facts confidently (§11). Options: a search tool, retrieval over your own documents, or accepting it knowingly. Doing nothing is legitimate for a personal question box. |
| 5 | **Dependency pins vs the course** | ✅ **Resolved 8 Aug 2026 — stay current** | Course pins FastAPI 0.115 / httpx 0.27 / psycopg 3.2. We run 0.141 / 0.28 / 3.3. Accepted cost: tracebacks won't match classmates', so cohort help is harder. |
| 6 | **Deploy shape** | ✅ **Resolved 8 Aug 2026 — match the course** | Render + Vercel split rather than Render-only. See §6.2 for the trade. |
| 7 | **Repo visibility** | Private | Public would match `publish_your_work.md` for a portfolio piece, and would also solve Vercel's repo access without granting the GitHub App. No secrets are in the repo. |

The API key already reaches every model these need — confirmed by listing models
on 8 Aug 2026. **These are scope choices, not capability limits.**

## 9. Deployment

### Shipped ✅ — 8 August 2026

| Resource | Value |
|---|---|
| Render web service | `srv-d9ra32qfngtc73ctjudg` · free · singapore · auto-deploy on `master` |
| Render Postgres | `dpg-d9ra1q2fngtc73ctho80-a` · free · singapore · PG **16.14** |
| Vercel project | `prj_IRlDJCZYjQNittWSAbm8cKJWle2O` · production alias `ai-app-bedtimestory.vercel.app` |
| GitHub | `simonraj79/ai-app-bedtimestory` (private), zero secrets committed |

Both migrations applied; `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL` and
`FRONTEND_ORIGINS` set on Render; health check `/healthz` →
`{"gemini":true,"postgres":true}`.

**Verified through a real browser**, not just curl: hub loads with no error
banner, Chat answered and persisted, Bedtime Story produced 179 correctly-toned
words and persisted, production CORS allows the Vercel origin (`200`) and refuses
others (`400`).

**The database has no public surface.** `DATABASE_URL` is Render's *internal*
connection string; `ipAllowList` is `[]`, so nothing outside Render's private
network can reach it. It was opened to a single `/32` for the migration and
closed immediately after.

### Also shipped 8 Aug 2026 ✅

1. **Vercel linked to GitHub** (milestone 13). Its GitHub App could not see the
   private repo, so the first frontend release was uploaded directly via the API.
   Now linked, so one `git push` deploys both halves and the drift risk is gone.
   `scripts/deploy_frontend.py` was deleted with it — that script existed only to
   cover the gap.
2. **Both deploy tokens rotated** (milestone 14). The Render one was exposed
   during setup; every token from that period is dead. Nothing in the repo reads
   either token any more.
3. **Google sign-in** (milestone 15). The OAuth client lives in Google Cloud
   project `dsai-mod-2-group-project` (number `722888382160`), owned by
   `<owner-account>` — **a different account from the machine's default Chrome
   profile**, which is the easiest confusing mistake available here. Two new env
   vars on Render, both `sync: false`: `GOOGLE_CLIENT_ID` (public — it also ships
   in `frontend/config.js`) and `ADMIN_EMAIL` (`<owner-account>`; private, not
   a credential).

   **Production migrated 8 Aug 2026**: `users` created, nullable `user_id` added
   to both tables, `(user_id, id DESC)` indexed on both. `ipAllowList` opened to
   a single `/32` and closed again — and *verified* closed by attempting a real
   connection and being refused, rather than by trusting the PATCH response.

### Remaining ⬜

One thing, and it blocks sign-in in production: **`GOOGLE_CLIENT_ID` in
`frontend/config.js` is still `REPLACE_WITH_CLIENT_ID.apps.googleusercontent.com`.**
Until the real value is committed and pushed, the deployed frontend cannot sign
anyone in — and because the failure happens at Google's end, the backend log
stays empty. Verify against the deployed file, not the local one.

After that, the next real work is decision #2 (child profiles).

**Live free-tier constraints:**

- Postgres **expires 2026-09-07**. `/healthz` will flip to `postgres: false` —
  and the `users` table goes with it, so **every account is lost**, not just the
  story log. Everyone signs in again into an empty history.
- The web service **sleeps after 15 minutes** idle; the next request takes
  30–60s. The frontend is on a CDN, so the *page* still loads instantly — only
  the first API call waits.

## 10. Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | Gemini key verified, smoke test passing | ✅ |
| 2 | App 1 Chat — single-turn, layered, running | ✅ |
| 3 | Postgres in Docker, both schemas applied | ✅ |
| 4 | App 2 Bedtime Story merged in behind the hub | ✅ |
| 5 | Real browser use, conversations persisting | ✅ 5 exchanges logged |
| 6 | Dependency audit and upgrade, re-verified | ✅ |
| 7 | Split into backend + `frontend/`, CORS verified | ✅ |
| 8 | Committed and pushed to GitHub, zero secrets | ✅ |
| 9 | Vercel project created | ✅ |
| 10 | Render deploy: service + Postgres + migrations | ✅ |
| 11 | Vercel deploy (direct upload) | ✅ |
| 12 | Two-pass URL wiring, verified live in a browser | ✅ |
| 13 | Vercel ↔ GitHub link (push-to-deploy both halves) | ✅ 8 Aug 2026, verified live |
| 14 | Rotate deploy tokens | ✅ 8 Aug 2026 |
| 15 | Google sign-in, per-user history, `/admin/usage` | ✅ 8 Aug 2026, production migrated |
| 16 | Child profiles | ⬜ decision #2 |
| 17 | Narration and/or illustrations | ⬜ decision #1 |

## 11. Known limits — by design, not defects

- **No memory.** The same question twice returns the same answer.
- **No grounding.** Asked "who won the world cup" on 8 Aug 2026, it named the
  **2022** tournament and hedged across four competitions.
- **No clarifying questions.** Ambiguous prompts get hedged answers, because
  there is no next turn in which to ask.
- **CORS is not authentication.** It stops other people's *websites* using this
  API through their visitors' browsers. `curl` ignores it entirely. ✅ **Acted on
  8 Aug 2026** — this was not theoretical: `curl /stories` with no token and no
  `Origin` returned 200 and 3,099 bytes of every child's story. Every generating
  route now requires a verified Google ID token and reads only that user's rows.
  CORS is still not authentication; it is now no longer the only thing there.
- **Sign-in is required to generate.** Someone who just opens the page cannot use
  the app — see §5.1 for what that cost. Pages render signed out with the button
  disabled rather than hiding the form.
- **Sign-in depends on `accounts.google.com` loading.** Content blockers and some
  networks break it. `config.js` says so instead of leaving a dead button, but
  there is no fallback.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Model produces something unsuitable for a child | System prompt constrains it; every story is stored and inspectable. Images would need a separate check. |
| Stale facts presented confidently | Documented in §11. Grounding is decision #4. |
| **Postgres dies 2026-09-07 — and now takes every account with it** | Hard date, now live, and **worse since sign-in shipped**: `users` lives in the same free database, so expiry loses accounts, not just the story log. `/healthz` shows `postgres: false` when it happens. Migrate to a paid tier or recreate before then. There is no export. **Top risk in the project.** |
| ~~Frontend silently drifts from backend~~ | ✅ **Closed 8 Aug 2026.** Vercel is linked to Git, so one `git push` deploys both halves and they can no longer diverge. Was the most likely near-term footgun. |
| Cold start makes it feel broken at bedtime | Free tier sleeps after 15 min. The frontend is on a CDN so the *page* loads instantly; the first API call waits 30–60s. `index.html` surfaces this rather than failing silently. |
| ~~Open API abuse~~ | ✅ **Closed 8 Aug 2026.** It was not low risk and it was not hypothetical: `curl /stories` returned every user's data. Every generating route now needs a verified Google ID token, and reads are scoped to the caller's `user_id`. The 401 is raised **before** Gemini is called, so unauthenticated traffic burns no quota either. |
| A single OAuth misconfiguration takes the whole app down | `GOOGLE_CLIENT_ID` is what `aud` is checked against, so a stale value rejects **every** sign-in with no error anywhere obvious. Bracket access makes a *missing* one a startup `KeyError`; a *wrong* one is silent. Authorized JavaScript origins must match exactly — no trailing slash, no path — and take ~5 min to propagate. |
| The consent screen is left in Testing | Caps at 100 hand-added test users. Publishing needs no Google review with only `openid`/`email`/`profile`, so there is no reason to stay in Testing — but Testing is the default. |
| Google's certs endpoint is unreachable | Verification is an outbound call per request. Returns `502` *"Could not reach Google to verify your sign-in"*, deliberately **not** 401 — telling a user with a valid token to sign in again is an unfixable loop from their side. |
| Model produces something unsuitable | Every story is stored and inspectable. Images would need a separate check. |
| Gemini free-tier rate limits | Single-household use is far below them. |
| API key leaks | Three secret files, all gitignored, verified with `git check-ignore` and a shape-based scan. The Render key was exposed once and rotated. ✅ **Both deploy tokens rotated 8 Aug 2026**, so every token exposed during setup is dead. Nothing in the repo reads them now that both hosts deploy from Git. |
| Divergence from the cohort's pins | Accepted in decision #5. If stuck, temporarily install the course's versions to reproduce a classmate's error. |

## 13. Immediate next steps

1. **Diarise 7 September 2026** — the free Postgres expires. This is now the only
   dated obligation, and the one thing that will take the app down if missed.
   Since milestone 15 it also destroys every account, so the decision to make
   before then is *paid tier or accept losing the users table*.
2. **Publish the OAuth consent screen** if it is still in Testing. Free, no
   review at these scopes, and it removes the 100-user cap before it is hit.

Milestones 13, 14 and 15 were all closed on 8 Aug 2026. The next real work is
decision #2 (child profiles) — the highest value-per-effort improvement
remaining, and now cheaper than it was: `users` exists, so a profile is a table
with a `user_id` rather than a new identity story.
