# Sourcer — Architecture Context for Migrating AI

> Written by Claude (Sonnet 4.6) after building and debugging this system.
> Target audience: the next AI agent taking over this codebase.

---

## 1. Original Technical Vision

Sourcer is an **autonomous AI recruitment pipeline**. The core idea:

1. Recruiter describes a vacancy (title, description, skills, geo, budget)
2. Gemini generates a search plan (LinkedIn Boolean queries, Telegram keywords, scoring rubric)
3. Agents scrape LinkedIn (Apify) + Telegram channels (Telethon) + optional XLSX upload
4. Two-stage scoring: embedding similarity filter → Gemini structured scoring
5. Recruiter reviews shortlist, creates outreach campaign
6. System sends messages via LinkedIn (Playwright) + Telegram (Telethon)
7. Replies come in, AI classifies intent, drafts responses (Copilot) or auto-sends (Autopilot)

The product has two distinct modes:
- **Copilot**: Human reviews every AI draft before sending
- **Autopilot**: AI sends + replies without human intervention (except for ambiguous/negative replies which are escalated)

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.115 + Uvicorn (async) |
| Task Queue | Celery 5.4 + Redis broker |
| Database | Supabase (PostgreSQL + pgvector) |
| Primary AI | Google Gemini 2.5 Flash (scoring, plan gen, reply classification) |
| Embeddings | Gemini `text-embedding-004` (768-dim) |
| Fallback AI | OpenRouter (OpenAI-compatible proxy) |
| LinkedIn Scraping | Apify actors (profile search + deep scrape) |
| LinkedIn Messaging | Playwright (headless Chromium, li_at cookie auth) |
| LinkedIn Inbox | `linkedin-api` library (Voyager internal API, read-only) |
| Telegram Scraping | Telethon (raw channel scrape + keyword filter) |
| Telegram Messaging | Telethon (async DM send) |
| Telegram Listener | Telethon async event loop (separate process) |
| Deduplication | rapidfuzz (fuzzy name match) + exact URL/email match |
| TF-IDF Fallback | scikit-learn (used when OpenRouter selected, no embeddings) |
| Frontend | Next.js 14.2 App Router + React 18.3 |
| Styling | Tailwind CSS 3.4 + CSS custom properties (dark theme) |
| Icons | lucide-react |

---

## 3. Folder Structure Logic

```
sourcer/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI route handlers (thin — just HTTP glue)
│   │   │   ├── routes_jobs.py       # /jobs — vacancy CRUD + pipeline control
│   │   │   ├── routes_outreach.py   # /outreach — campaigns, leads, conversations
│   │   │   └── routes_admin.py      # /admin — credentials + pipeline logs
│   │   ├── core/
│   │   │   ├── config.py     # Pydantic Settings — all env vars live here
│   │   │   ├── db.py         # Supabase client singleton
│   │   │   ├── celery_app.py # Celery app factory + beat schedule
│   │   │   └── logging.py    # Structured logger factory
│   │   ├── schemas/          # Pydantic models (request/response shapes)
│   │   ├── services/         # Business logic called by routes
│   │   │   ├── jobs.py       # create_job_with_plan, get_job, list_candidates
│   │   │   └── dedup.py      # Three-pass deduplication logic
│   │   ├── scoring/
│   │   │   ├── gemini.py     # Gemini API: plan gen, scoring, embeddings, retry
│   │   │   └── pipeline.py   # Two-stage scoring orchestration
│   │   ├── scrapers/
│   │   │   ├── linkedin_apify.py    # Apify actor → candidate profiles
│   │   │   ├── linkedin_deep.py     # Phase 2 deep profile enrichment via Apify
│   │   │   ├── telegram.py          # Telethon channel scraper
│   │   │   └── file_ingest.py       # XLSX/CSV → normalized candidates
│   │   ├── outreach/
│   │   │   ├── sender.py            # Multi-channel send dispatch
│   │   │   ├── composer.py          # Template → rendered message
│   │   │   ├── linkedin_playwright.py  # Headless browser messaging
│   │   │   ├── linkedin_inbox.py    # Voyager inbox polling (read-only)
│   │   │   ├── reply_classifier.py  # Classify reply intent via Gemini
│   │   │   └── telegram_listener.py # Async DM listener event loop
│   │   └── tasks/            # Celery tasks (long-running async work)
│   │       ├── pipeline.py   # Phase 1: scrape → dedupe → embed → score
│   │       ├── deep_scan.py  # Phase 2: Apify deep enrichment + re-score
│   │       ├── score_now.py  # Re-score without scraping
│   │       ├── outreach.py   # Batch campaign send
│   │       ├── poll_inbox.py # LinkedIn inbox poller (beat task, 30min)
│   │       └── reply_pipeline.py  # AI draft generation for replies
│   ├── sessions/             # Telethon session files (.session binary)
│   ├── data/                 # Uploaded files, temp exports
│   └── scripts/
│       ├── telegram_login.py # One-time interactive Telegram auth
│       └── run_telegram_listener.py  # Entry point for listener process
├── frontend/
│   ├── app/                  # Next.js App Router pages
│   │   ├── layout.tsx        # Root nav + global layout
│   │   ├── page.tsx          # Sourcing wizard (3-step: Vacancy → Sources → Launch)
│   │   ├── jobs/[id]/        # Job detail: plan view, candidates table, pipeline controls
│   │   ├── outreach/
│   │   │   ├── page.tsx      # Campaigns list with live stats
│   │   │   ├── new/          # Campaign creation form
│   │   │   ├── [id]/         # Campaign detail: lead table, Kanban, slide-out thread
│   │   │   ├── inbox/        # Unified message inbox
│   │   │   └── review/       # Copilot approval queue
│   │   └── admin/
│   │       ├── credentials/  # API key status + update
│   │       └── logs/         # Pipeline run audit log
│   ├── components/ui.tsx     # ALL shared UI components in ONE file (see warning below)
│   └── lib/api.ts            # API client + all TypeScript types
└── docker-compose.yml        # Full stack: redis, api, worker, beat, tg-listener, frontend
```

---

## 4. Complex Algorithms & Hidden Dependencies

### 4.1 Two-Stage Scoring Pipeline (CRITICAL — understand before touching)

Located in `backend/app/scoring/pipeline.py` and `backend/app/tasks/pipeline.py`.

**Stage 1 — Embedding Filter:**
- Generate a 768-dim embedding of the job description (once per pipeline run)
- Generate embeddings for all scraped candidates (batched)
- Compute cosine similarity for each candidate vs job embedding
- Drop the bottom `EMBEDDING_FILTER_PERCENTILE` (default 30%) — this is a SOFT filter
- Only candidates above this percentile proceed to Stage 2

**Stage 2 — LLM Scoring:**
- Each surviving candidate is scored by Gemini using the job's `rubric` (JSON schema generated during job creation)
- Rubric is generated ONCE at job creation (`generate_plan()`) and stored in `jobs.rubric`
- Score is 0-100 + dimensional scores + red_flags[]
- Drop candidates below `MIN_GEMINI_SCORE` (default 50)

**⚠️ Warning:** The rubric lives in `jobs.rubric` (jsonb column). If the job is re-created or the plan re-generated, the rubric changes and old scores become incomparable to new ones. Never auto-regenerate plans without clearing old scores.

### 4.2 Gemini API Key Rotation

Located in `backend/app/scoring/gemini.py`.

- `GEMINI_API_KEYS` env var can contain multiple comma-separated keys
- A global counter tracks per-key daily request count
- On `ResourceExhausted` error → automatically rotate to next key
- Rate limiter enforces 10 req/min globally across all keys
- **Fallback order:** Primary key → Key pool rotation → Raise

**⚠️ Warning:** The rate limiter state is in-memory (lost on worker restart). Under heavy load with multiple Celery workers, rate limiting is PER-WORKER, not global. This can cause 429s if running 4+ workers simultaneously.

### 4.3 Deduplication (Three-Pass)

Located in `backend/app/services/dedup.py`.

**Pass 1:** Exact LinkedIn URL or Telegram username or email match → merge records (preserve non-empty fields from both)

**Pass 2:** Fuzzy name match using rapidfuzz `token_set_ratio ≥ 92` → merge if AND only if no conflicting URLs

**Pass 3:** `dedup_key` stored per candidate in DB — prevents re-importing the same person across pipeline runs for the same job

**⚠️ Warning:** Fuzzy dedup at 92% threshold is aggressive. "John Smith" and "Jon Smith" will merge. This is intentional (CIS names + transliteration). Do NOT lower this without testing on Cyrillic names.

### 4.4 LinkedIn Playwright Messaging

Located in `backend/app/outreach/linkedin_playwright.py`.

- Uses `li_at` cookie (NOT OAuth) — pasted manually into Credentials page
- Launches headless Chromium → navigates to profile → clicks Message → types → sends
- Random delay between sends: `LI_SEND_MIN_DELAY` to `LI_SEND_MAX_DELAY` (default 300s–900s)
- On failure: error is written to `outreach_leads.last_message` (used to surface in UI)

**⚠️ WARNING:** The `li_at` cookie expires randomly (LinkedIn detects new IPs). The system has no automatic detection — it records the error string to `last_message`. A previous bug was that these error strings (`[ERROR] Could not find 'Message' button...`) appeared in the Inbox as conversation previews. This has been fixed (backend now filters `last_message LIKE '[ERROR]%'` from the inbox query). Do NOT remove this filter.

**⚠️ WARNING:** The `Message` button selector changes with LinkedIn A/B tests. If sends suddenly break, this is the first thing to check in `linkedin_playwright.py`.

### 4.5 Telegram Session Detection

Located in `backend/app/api/routes_admin.py` (`get_credentials`).

Session file lives at `backend/sessions/sourcer_session.session`. The detection logic uses `__file__`-relative path resolution (added after bug where relative CWD paths didn't resolve from uvicorn's working directory). Do NOT change this to simple relative paths again.

```python
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
session_path = os.path.join(_backend_dir, "sessions", "sourcer_session.session")
```

### 4.6 Supabase `maybe_single()` Bug

**CRITICAL — affects any code that does `.maybe_single()` on the Supabase Python client.**

The Supabase Python client's `.maybe_single()` throws `APIError: {'code': '204', 'message': 'Missing response'}` when the query returns 0 rows. This is a known library bug.

**Pattern to ALWAYS use instead:**
```python
# WRONG — will throw on 0 results:
result = sb.table("foo").select("id").eq("id", x).maybe_single().execute()

# CORRECT:
result = sb.table("foo").select("id").eq("id", x).limit(1).execute()
if not result.data:
    raise HTTPException(404, "Not found")
```

Every existence check in `routes_outreach.py` and `routes_admin.py` uses `.limit(1).execute()` for this reason.

### 4.7 Frontend useEffect / Loading State Pattern

**A known bug was fixed in `frontend/app/outreach/page.tsx`.**

The original code had `campaigns.length` in the `useEffect` dependency array:
```typescript
// OLD — BROKEN: caused infinite loading after navigation
useEffect(() => {
  load();
  const iv = setInterval(load, hasActive ? 8000 : 20000);
  return () => clearInterval(iv);
}, [load, campaigns.length]); // ← campaigns.length here is the problem
```

When campaigns loaded (length 0 → N), the effect re-fired, starting a second concurrent `load()`. In Next.js App Router's soft navigation, this race condition left `loading` permanently `true`.

**Fixed pattern — use this everywhere:**
```typescript
useEffect(() => {
  load();
  const iv = setInterval(load, 10000);
  return () => clearInterval(iv);
}, [load]); // ← stable ref only
```

Do NOT add array lengths, object properties, or derived values to `useEffect` dep arrays. Use `useRef` or restructure logic instead.

### 4.8 Celery + SQLite "Database is Locked" Error

The pipeline_runs table will occasionally show `database is locked` errors. This is not SQLite — it's a Supabase connection pool issue under concurrent Celery workers. The DB can handle it, but if you see cascading lock errors, reduce worker concurrency:

```bash
celery -A app.core.celery_app worker --concurrency=2
```

### 4.9 Inbox Filtering (Error Messages)

The `GET /outreach/inbox` endpoint filters leads whose `last_message` starts with `[ERROR]`:

```python
.not_.like("last_message", "[ERROR]%")
```

This exists because LinkedIn Playwright failures write their exception message to `last_message`. Without this filter, the inbox fills with error strings instead of actual conversations. Do NOT remove this filter. If you change error message formats in `linkedin_playwright.py`, update this filter.

---

## 5. Unimplemented Features & Shortcuts

### 5.1 INCOMPLETE: Credentials Not Persisted to Disk

The `PATCH /admin/credentials` endpoint updates environment variables **in-memory only**. On backend restart, all credential changes are lost. The endpoint explicitly notes this:

> "This writes values to the running process environment only. For persistence across restarts, the user must update their .env file."

**To fix:** Write changes to `.env` file using `python-dotenv`'s `set_key()` function, or persist to a `settings` DB table.

### 5.2 INCOMPLETE: No Authentication / Authorization

The entire API is unauthenticated. Anyone who can reach `localhost:8000` can read all data, delete campaigns, and send messages. This was intentional for local-only use.

**To fix:** Add `Authorization: Bearer <token>` header validation to FastAPI routes, or use Supabase Auth with JWT verification.

### 5.3 INCOMPLETE: LinkedIn Inbox Polling is One-Way

The `poll_linkedin_inbox` Celery beat task runs every 30 minutes and reads the LinkedIn inbox via the Voyager API (`linkedin-api` library). However:
- It only reads NEW messages since last poll — no backfill on first run
- The `linkedin-api` library is unofficial and breaks when LinkedIn changes their internal API
- If the poll fails, replies are silently missed (no alerting)

**To fix:** Add error alerting to operator Telegram username when inbox poll fails. Also add a "last polled at" timestamp to the admin/credentials page.

### 5.4 INCOMPLETE: Telegram 2FA Not Supported

`scripts/telegram_login.py` prompts for verification code but does NOT handle accounts with Two-Factor Authentication (2FA/TOTP). If the account has 2FA enabled, login will fail silently.

**To fix:** Add `password=` parameter to Telethon's `sign_in()` call and prompt for it.

### 5.5 INCOMPLETE: Apollo.io Scraper Stub

`backend/app/scrapers/apollo.py` exists and is referenced in pipeline config but the actual scraping logic may be incomplete or use a placeholder API call. Check before relying on it.

### 5.6 INCOMPLETE: XLSX Column Auto-Detection Uses Gemini

The `POST /outreach/leads/preview-xlsx` endpoint sends column headers to Gemini to detect field mappings. This costs API calls and fails if GEMINI_API_KEY is not set. There's no local fallback for column detection.

**To fix:** Add a heuristic rule-based column matcher as fallback (e.g., "name" → `full_name`, "telegram" → `telegram_url`).

### 5.7 SHORTCUT: No Job Queue Visibility

Once a pipeline task is running, the only progress visibility is through `pipeline_runs` rows (polled every 2s by the frontend). There's no real-time progress events (no WebSockets, no SSE). The Celery task ID is returned from `POST /jobs/{id}/run` but is not used by the frontend.

**To fix:** Add Server-Sent Events to push pipeline_runs updates in real-time, or integrate Celery's built-in progress reporting with task meta.

### 5.8 SHORTCUT: Supabase Service Role Key in Backend

The backend uses `SUPABASE_SERVICE_ROLE_KEY` which bypasses Row Level Security. This is fine for a local tool but means RLS policies in Supabase are irrelevant — all backend operations have unrestricted access.

### 5.9 SHORTCUT: No Message Delivery Confirmation

When `sender.py` dispatches a Telegram or LinkedIn message, success is determined by whether the API call didn't throw. There's no confirmation that the candidate actually received the message (e.g., blocked, DMs disabled, etc.). LinkedIn Playwright may silently fail if the messaging dialog changes structure.

### 5.10 SHORTCUT: `setLoading(false)` Pattern in Frontend

All frontend pages use a `loading` state initialized to `true` (`useState(true)`). The `load()` function ONLY calls `setLoading(false)` — it does NOT call `setLoading(true)` at the start. This means:
- Initial page load: shimmer shows (from `useState(true)`) until first `load()` completes → correct
- Interval refreshes: silent (no shimmer) → correct

**Do NOT add `setLoading(true)` at the top of `load()` functions** unless you want the shimmer to flash every refresh interval. The exception is pages that show a loading indicator separate from the data area (like the logs page which explicitly shows a refresh spinner).

### 5.11 SHORTCUT: Campaign Stats via Batch Join (No DB View)

`GET /outreach/campaigns` computes `total_leads`, `sent_count`, `replied_count` by:
1. Fetching all campaigns
2. Fetching ALL leads for those campaign IDs in one query
3. Grouping in Python with `defaultdict` + `Counter`

This is efficient for small datasets (< 10k leads) but will slow down significantly at scale. A proper Postgres VIEW or materialized view with aggregates would be cleaner.

---

## 6. Environment Variables Reference

```bash
# ── Telegram ──────────────────────────────────────────
TELEGRAM_API_ID=          # from my.telegram.org
TELEGRAM_API_HASH=        # from my.telegram.org
TELEGRAM_PHONE=           # international format: +1234567890

# ── LinkedIn ──────────────────────────────────────────
LI_AT_COOKIE=             # paste from browser DevTools → Application → Cookies
LI_HEADLESS=true          # set false to watch browser during debug
LI_SEND_MIN_DELAY=300     # seconds between LinkedIn sends (min)
LI_SEND_MAX_DELAY=900     # seconds between LinkedIn sends (max)

# ── Apify ─────────────────────────────────────────────
APIFY_API_KEY=
APIFY_LINKEDIN_ACTOR=harvestapi/linkedin-profile-search

# ── Supabase ──────────────────────────────────────────
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=   # used by backend; bypasses RLS

# ── Gemini ────────────────────────────────────────────
GEMINI_API_KEY=              # primary key
GEMINI_API_KEYS=key1,key2    # optional rotation pool
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_EMBED_MODEL=gemini-embedding-001
AI_PROVIDER=gemini           # or: openrouter

# ── OpenRouter (alternative to Gemini) ────────────────
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemini-2.0-flash-001

# ── Redis / Celery ────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ── Scoring Thresholds ────────────────────────────────
EMBEDDING_FILTER_PERCENTILE=0.30   # drop bottom 30% by embedding similarity
MIN_GEMINI_SCORE=50                # drop candidates scoring below this

# ── Misc ──────────────────────────────────────────────
APP_ENV=dev
API_PORT=8000
FRONTEND_URL=http://localhost:3000
OPERATOR_TELEGRAM_USERNAME=@yourusername   # gets pinged on li_at expiry
LOG_LEVEL=INFO
```

---

## 7. Database Schema Quick Reference

| Table | Key Columns |
|---|---|
| `jobs` | id, title, description, skills[], geo, tg_channels[], linkedin_boolean, rubric (jsonb), status, stats |
| `candidates` | id, job_id, source, full_name, headline, embedding (vector 768), embed_similarity, gemini_score, gemini_dimensions (jsonb), red_flags[], status |
| `pipeline_runs` | id, job_id, stage, status (started\|ok\|error), count, message, started_at, ended_at |
| `outreach_campaigns` | id, job_id, name, tg_template, li_template, screening_questions[], outreach_mode (copilot\|autopilot), status |
| `outreach_leads` | id, campaign_id, full_name, linkedin_url, telegram_url, status (pending\|sent\|replied\|qualified\|rejected), last_message, ai_intent, ai_draft, needs_review |
| `outreach_messages` | id, lead_id, direction (sent\|received), channel (telegram\|linkedin), text, is_auto |

**pgvector function:** `match_candidates(job_id, query_embedding, match_count)` — cosine similarity search over `candidates.embedding`

---

## 8. Process Map (How Everything Connects)

```
User fills vacancy form
        │
        ▼
POST /jobs  →  create_job_with_plan()  →  Gemini generates plan
        │                                  (linkedin_queries, tg_keywords, rubric)
        ▼
POST /jobs/{id}/run
        │
        ▼
Celery: run_pipeline()
        ├── scrape LinkedIn via Apify
        ├── scrape Telegram via Telethon
        ├── ingest uploaded XLSX
        ├── dedup (3-pass)
        ├── Stage 1: embed + percentile filter
        └── Stage 2: Gemini score + persist to candidates table
        │
        ▼
(Optional) POST /jobs/{id}/deep-scan
        │
        ▼
Celery: run_deep_scan()
        ├── Apify deep profile → positions, educations
        └── re-score with richer context
        │
        ▼
User creates outreach campaign
        │
        ▼
Campaign sends messages (Playwright / Telethon)
        │
        ├── Telegram replies → telegram_listener.py (separate process)
        │         └── classifies intent → sets needs_review if copilot
        │
        └── LinkedIn replies → poll_linkedin_inbox (Celery beat, 30min)
                  └── classifies intent → sets needs_review if copilot
                                │
                                ▼
                    Copilot: review/page.tsx → human approves draft
                    Autopilot: reply sent automatically
```

---

*Last updated: April 2026 by Claude Sonnet 4.6*
