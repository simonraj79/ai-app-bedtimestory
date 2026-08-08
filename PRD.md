# PRD — AI Apps

**Status:** V1 built and verified locally; deploy in progress · **Last updated:** 8 August 2026
**Owner:** Simon · **Related:** `CLAUDE.md` (conventions, insights, gotchas), `README.md` (how to run)

---

## 1. What this is

A small family of **single-turn** AI apps behind a hub page. App 1 is the Single
Turn Chat — the foundation. App 2 is the Bedtime Story Generator: the same
architecture pointed at a narrower job.

| # | App | Page | Endpoint | Table | Status |
|---|---|---|---|---|---|
| 1 | 💬 Chat | `chat.html` | `POST /ask` | `interactions` | ✅ Built, in real use |
| 2 | 🌙 Bedtime Story | `story.html` | `POST /story` | `stories` | ✅ Built |

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
| Chat latency | < 5s | ~2.5s |
| Story latency | < 15s | ~6–8s |
| Story length | 150–250 words | ~185 |
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

### Ready ✅

- `render.yaml` — web service + free Postgres, `healthCheckPath: /healthz`,
  `GEMINI_API_KEY` and `FRONTEND_ORIGINS` as `sync: false`, `DATABASE_URL` via
  `fromDatabase` — so the committed blueprint holds **zero secrets**
- `Procfile`, `vercel.json`, `.vercelignore`, `.python-version` (3.13)
- Start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT` tested locally
- Code pushed to `simonraj79/ai-app-bedtimestory` (private), zero secrets
- Render token verified (owner `tea-csps46i3esus73eojjp0`)
- Vercel token verified; project `ai-app-bedtimestory`
  (`prj_IRlDJCZYjQNittWSAbm8cKJWle2O`) created under `simon-rajs-projects`

### Remaining ⬜

1. Grant Vercel's GitHub App access to the private repo, then link it
2. Render Blueprint deploy; set `GEMINI_API_KEY`; apply both migrations
3. Set `BACKEND_URL` in `frontend/config.js` → commit → push
4. Deploy Vercel; set `FRONTEND_ORIGINS` on Render to the Vercel URL
5. Revoke both deploy tokens

**Known free-tier constraints:**

- Render Postgres **expires 30 days after creation** — create at deploy time
- Render web services **sleep after 15 minutes** idle; first request 30–60s
- Render Blueprints read `render.yaml` from a **pushed, accessible** repo

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
| 10 | Vercel ↔ GitHub link | ⬜ needs repo access |
| 11 | Render deploy + migrations | ⬜ starts the 30-day clock |
| 12 | Two-pass URL wiring, live end to end | ⬜ |
| 13 | Child profiles | ⬜ decision #2 |
| 14 | Narration and/or illustrations | ⬜ decision #1 |

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
| Free Postgres expires mid-use | 30-day clock starts at creation. Note the date; `/healthz` shows `postgres: false`. |
| Cold start makes it feel broken at bedtime | Free tier sleeps after 15 min. The frontend is on a CDN so the *page* loads instantly; the first API call waits 30–60s. |
| Open API abuse | CORS is not a control here. Single-household use makes it low risk, but the endpoint is public once deployed. |
| Gemini free-tier rate limits | Single-household use is far below them. |
| API key leaks | Three secret files, all gitignored and verified. The Render key was exposed once and rotated. **Revoke both deploy tokens after deploying.** |
| Divergence from the cohort's pins | Accepted in decision #5. If stuck, temporarily install the course's versions to reproduce a classmate's error. |

## 13. Immediate next step

Milestone 10 — grant Vercel access to the private repo (or make it public), then
Render (milestone 11) and the two-pass wiring.
