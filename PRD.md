# PRD — AI Apps

**Status:** V1 built, verified locally, ready to deploy · **Last updated:** 8 August 2026
**Owner:** Simon · **Related:** `CLAUDE.md` (conventions, insights, gotchas), `README.md` (how to run)

---

## 1. What this is

One project hosting a small family of **single-turn** AI apps behind a hub page.
App 1 is the Single Turn Chat — the foundation. App 2 is the Bedtime Story
Generator: the same architecture pointed at a narrower job.

| # | App | Page | Endpoint | Table | Status |
|---|---|---|---|---|---|
| 1 | 💬 Chat | `/chat` | `POST /ask` | `interactions` | ✅ Built, in real use |
| 2 | 🌙 Bedtime Story | `/bedtime` | `POST /story` | `stories` | ✅ Built |

## 2. Problem

Two related needs, one architecture:

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

Assumed a **single household**, no accounts. Revisit only if someone else asks
to use it.

## 5. Scope

### V1 — built ✅

- Hub page listing the apps
- **App 1 Chat:** question → short answer (under 80 words) → saved → 10 most
  recent listed
- **App 2 Bedtime Story:** child's name + theme → ~200-word gentle story, simple
  vocabulary, nothing frightening, ends with the child asleep → saved → 10 most
  recent listed
- `/healthz` reporting Gemini and Postgres separately
- Loud startup failure on missing configuration
- `render.yaml` blueprint, start command verified

### Explicitly out of scope for V1

| Not doing | Why |
|---|---|
| Conversation / "continue the story" | Makes it multi-turn: session keys, growing token cost, per-user isolation. A separate product decision, not a tweak. |
| Grounding / web search | Would fix stale answers (§8, decision 4) but is a distinct feature with its own failure modes. |
| Accounts and login | Large amount of work unrelated to the product; wrong for a bedtime device. |
| Streaming tokens as they generate | 2–8s is tolerable. Adds real complexity. |
| Illustrations, narration, PDF | See §8 — decided, not overlooked. |
| Tests | Not in V1, per the course doctrine this inherits. |

## 6. Design

### 6.1 Single-turn, deliberately

Each request sends exactly `[systemInstruction, one user message]`. The model has
no memory across requests. The tables are a **library for the human**, never
context for the prompt.

**Confirmed observationally:** rows 2 and 3 of `interactions` are the same
question asked twice, with near-identical answers. The model had no idea it had
just answered.

This descends from the course app (`fastapi-ollama-postgres-cohort`,
`module5-readiness-checklist.md:253`: *"Both courses build a single-turn LLM app —
one question in, one answer out"*), with two swaps: Gemini replaces Ollama, and
the cloud replaces localhost.

### 6.2 The system prompts are the product

`CHAT_SYSTEM_PROMPT` and `STORY_SYSTEM_PROMPT` carry length, tone, vocabulary,
safety, and shape. They do more work than any code in the repo. Child-safety for
app 2 lives entirely in its prompt.

### 6.3 Layered so the provider is swappable

`main.py` knows only `call_gemini(question)` and
`generate_story(child_name, theme)`; both funnel through one `ask_gemini()` that
owns the HTTP call. Everything Gemini-shaped is in one file — which is why moving
from Ollama to Gemini touched exactly one file. Preserve this.

### 6.4 One project, one database, one deploy

Both apps share a FastAPI instance, a Postgres database, and a deploy. Adding an
app means a prompt, a service, schemas, a template, a hub card, and a migration.

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

`model_name` is stored per row on purpose: when the model changes you can tell
which rows came from which, and whether quality moved.

### 6.6 API

See `README.md` for the full table. Errors: `400` blank input · `422` malformed
body · `502` Gemini or Postgres unreachable. `/healthz` always returns 200 — it
is a diagnostic, not a gate.

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
| Secrets in repo | Zero | Verified with `git check-ignore`; 21 files staged, none secret |

## 8. Open decisions

Genuinely undecided. V1 assumes the middle column and works today.

| # | Decision | V1 assumption | Alternatives |
|---|---|---|---|
| 1 | **Output modality (app 2)** | Text only | **Narration** (`gemini-3.1-flash-tts-preview`) — arguably the real killer feature for bedtime, eyes closed. Adds audio storage; Render's free disk is ephemeral, so stream it or store bytes in Postgres. **Illustrations** (`imagen-4.0-fast-generate-001`, `nano-banana-pro-preview`) — high delight, slowest and priciest call, needs its own child-safety pass since images don't inherit the prompt. **PDF keepsake** — no AI cost, pure templating. |
| 2 | **Child profiles (app 2)** | None — name and theme typed each time | Store name, age, favourite characters once and feed them into the system prompt. Where personalisation stops being a gimmick. Small change: a `children` table + FK. Likely the best value-per-effort addition. |
| 3 | **Merge the two apps into one project** | — | ✅ **Resolved 8 Aug 2026** — merged. One service, one database, one deploy. |
| 4 | **Grounding for app 1** | Ungrounded | The model's knowledge ends before 2026 and it answers stale facts confidently (§11). Options: a search tool, retrieval over your own documents, or simply accepting it and knowing the limit. Doing nothing is a legitimate choice for a personal question box. |

The API key already reaches every model these need — confirmed by listing models
on 8 Aug 2026. **These are scope choices, not capability limits.**

## 9. Deployment

**Target: Render only.** FastAPI web service + managed Postgres, one account, one
deploy, no CORS.

The parent course splits the frontend onto Vercel and the backend onto Render.
That split is the origin of most of its documented student failures —
`BACKEND_URL` typos, blocked CORS preflight, Vercel trying to deploy the Python
backend (`setup_walkthrough.md:610`). Keeping FastAPI serving its own templates
deletes that entire failure class at no functional cost.

### Ready ✅

- `render.yaml` — web service + free Postgres, `healthCheckPath: /healthz`
- Start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT` tested locally
- No code hardcodes host or port
- `GEMINI_API_KEY` declared `sync: false`; `DATABASE_URL` via `fromDatabase` — so
  the committed blueprint contains **zero secrets**
- Render API key rotated and verified (owner `tea-csps46i3esus73eojjp0`)
- Git repo initialised; `.env` and `.render.env` confirmed excluded

### Remaining ⬜

1. First commit (staged, not committed)
2. Push to GitHub — Blueprints read `render.yaml` **from a repo**
3. Render → New → Blueprint → select repo
4. Set `GEMINI_API_KEY` in the dashboard
5. Apply both migrations to the managed database

**Known free-tier constraints:**

- Postgres **expires 30 days after creation** — create it at deploy time, not before
- Web services **sleep after 15 minutes** idle; first request after takes 30–60s
- Render API keys are ~32–40 chars; a 20-char one is a truncated paste → `401`

## 10. Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | Gemini key verified, smoke test passing | ✅ |
| 2 | App 1 Chat — single-turn, layered, running | ✅ |
| 3 | Postgres in Docker, both schemas applied | ✅ |
| 4 | App 2 Bedtime Story merged in behind the hub | ✅ |
| 5 | Real browser use, conversations persisting | ✅ 5 exchanges logged |
| 6 | `render.yaml` written and start command verified | ✅ |
| 7 | Commit, push, deploy to Render | ⬜ next |
| 8 | Child profiles | ⬜ decision #2 |
| 9 | Narration and/or illustrations | ⬜ decision #1 |

## 11. Known limits — by design, not defects

Observed in real use and worth stating plainly:

- **No memory.** The same question twice returns the same answer. The model does
  not know it just replied.
- **No grounding.** Asked "who won the world cup" on 8 Aug 2026, it named the
  **2022** tournament as most recent and hedged across four different
  competitions. Its training data ends before 2026 and nothing supplies current
  facts.
- **No clarifying questions.** Ambiguous prompts get hedged answers covering
  every interpretation, because there is no next turn in which to ask.

Each maps to a real feature (retrieval, multi-turn) that was deliberately left
out of V1. Knowing where the edges are is worth more than a version that hides
them.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Model produces something unsuitable for a child | System prompt constrains it; every story is stored and inspectable. Images would need a separate check. |
| Stale facts presented confidently | Documented in §11. Grounding is decision #4. |
| Free Postgres expires mid-use | 30-day clock starts at creation. Note the date; `/healthz` shows `postgres: false`. |
| Cold start makes it feel broken at bedtime | Free tier sleeps after 15 min. Accept the 30–60s wake, or pay for always-on. |
| Gemini free-tier rate limits | Single-household use is far below them. Revisit if shared. |
| API key leaks | `.env` and `.render.env` gitignored, **verified with `git check-ignore`**. The Render key was briefly in `.env` and exposed — it has been rotated. Re-verify before every push. |

## 13. Immediate next step

Milestone 7: commit, push to GitHub, deploy the Blueprint. Everything it depends
on is done.
