# PRD — AI Apps

**Status:** ✅ **V1 shipped — live in production** · **Last updated:** 8 August 2026
**Owner:** Simon · **Related:** `CLAUDE.md` (conventions, insights, gotchas), `README.md` (how to run)

| | URL |
|---|---|
| **Frontend** | <https://ai-app-bedtimestory.vercel.app> |
| **Backend** | <https://ai-app-bedtimestory.onrender.com> |

⚠️ Free Postgres **expires 2026-09-07**. ⚠️ Vercel auto-deploy not yet wired —
`git push` redeploys the backend only.

---

## 1. What this is

A small family of **single-turn** AI apps behind a hub page. App 1 is the Single
Turn Chat — the foundation. App 2 is the Bedtime Story Generator: the same
architecture pointed at a narrower job.

| # | App | Page | Endpoint | Table | Status |
|---|---|---|---|---|---|
| 1 | 💬 Chat | `chat.html` | `POST /ask` | `interactions` | ✅ **Live** |
| 2 | 🌙 Bedtime Story | `story.html` | `POST /story` | `stories` | ✅ **Live** |

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
| Simon (operator) | Fast, private, no login friction. A record he owns. |
| Child (audience, app 2) | A story with their name in it, that isn't frightening. |

Assumed a **single household**, no accounts.

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
| Accounts and login | Large, unrelated to the product, wrong for a bedtime device. |
| Streaming tokens | 2–8s is tolerable. Adds real complexity. |
| Illustrations, narration, PDF | See §8 — decided, not overlooked. |
| Tests | Not in V1, per the course doctrine this inherits. |

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
| Secrets in repo | Zero | Verified with `git check-ignore` and a shape-based key scan |

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

### Remaining ⬜

1. **Link Vercel to GitHub** — its GitHub App cannot see the private repo, so the
   frontend was uploaded directly via the API. Until linked, `git push`
   redeploys the **backend only** and the frontend can silently drift.
   Fix: <https://github.com/settings/installations> → Vercel → Configure → add
   the repo. (Or make the repo public — decision #7.)
2. **Revoke both deploy tokens.** No longer needed; the Render one was exposed
   during setup.

**Live free-tier constraints:**

- Postgres **expires 2026-09-07**. `/healthz` will flip to `postgres: false`.
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
| 13 | Vercel ↔ GitHub link (push-to-deploy both halves) | ⬜ needs repo access |
| 14 | Revoke deploy tokens | ⬜ |
| 15 | Child profiles | ⬜ decision #2 |
| 16 | Narration and/or illustrations | ⬜ decision #1 |

## 11. Known limits — by design, not defects

- **No memory.** The same question twice returns the same answer.
- **No grounding.** Asked "who won the world cup" on 8 Aug 2026, it named the
  **2022** tournament and hedged across four competitions.
- **No clarifying questions.** Ambiguous prompts get hedged answers, because
  there is no next turn in which to ask.
- **CORS is not authentication.** It stops other people's *websites* using this
  API through their visitors' browsers. `curl` ignores it entirely — anyone can
  still call the API directly. If that ever matters, it needs real auth.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Model produces something unsuitable for a child | System prompt constrains it; every story is stored and inspectable. Images would need a separate check. |
| Stale facts presented confidently | Documented in §11. Grounding is decision #4. |
| **Postgres dies 2026-09-07** | Hard date, now live. `/healthz` shows `postgres: false` when it happens. Migrate to a paid tier or recreate before then. Diarise it. |
| **Frontend silently drifts from backend** | Vercel is not linked to Git, so `git push` updates only the backend. Any frontend change needs a manual upload until milestone 13. This is the most likely near-term footgun. |
| Cold start makes it feel broken at bedtime | Free tier sleeps after 15 min. The frontend is on a CDN so the *page* loads instantly; the first API call waits 30–60s. `index.html` surfaces this rather than failing silently. |
| Open API abuse | CORS is not a control — `curl` ignores it. The endpoint is public now that it is deployed. Single-household use makes it low risk; if that changes, it needs real auth. |
| Model produces something unsuitable | Every story is stored and inspectable. Images would need a separate check. |
| Gemini free-tier rate limits | Single-household use is far below them. |
| API key leaks | Three secret files, all gitignored, verified with `git check-ignore` and a shape-based scan. The Render key was exposed once and rotated. **Both deploy tokens still live — revoke them (milestone 14).** |
| Divergence from the cohort's pins | Accepted in decision #5. If stuck, temporarily install the course's versions to reproduce a classmate's error. |

## 13. Immediate next steps

1. **Revoke both deploy tokens** (milestone 14) — nothing needs them now.
2. **Link Vercel to GitHub** (milestone 13) — one click, then push-to-deploy
   works on both halves and risk #2 disappears.
3. Diarise **7 September 2026**.

After that, V1 is genuinely done and the next real work is decision #2 (child
profiles) — the highest value-per-effort improvement remaining.
