# Sourcer Agent - Development & Architecture Handover Log

This document serves as a handover log for the "OpenCode" structural rework. It details the recent development phases, architectural decisions, bug fixes, and system fragilities encountered during the collaborative sessions with AI models (Claude Sonnet & Google Gemini/Antigravity).

---

## 1. Technical Vision & Tech Stack
**Vision:** A fully autonomous recruitment pipeline that can take an arbitrary job description, scrape candidates from multiple sources (Telegram, LinkedIn/SalesNav via XLSX, Apollo), pre-filter them using embeddings, score them using LLMs, and manage automated outreach and inbox replies.

**Tech Stack:**
*   **Backend:** Python 3.11+, FastAPI, Celery (Workers & Beat), Redis (Broker/Backend).
*   **Database:** Supabase (PostgreSQL with `pgvector` for embeddings).
*   **Frontend:** Next.js (React), Tailwind CSS, Lucide Icons.
*   **AI/LLM:** OpenRouter routing to Gemini 2.5 Pro (and Gemini Embedding 001).
*   **Scraping & Outreach:** Telethon (Telegram DMs and channels), Playwright (LinkedIn Outreach), PhantomBuster/Apify (Legacy/Deprecated).

---

## 2. Folder Structure Logic
The repository is split into a strict `frontend/` and `backend/` monorepo structure.
*   **`frontend/app/`**: Next.js App Router.
    *   `/campaign/`: The sourcing wizard (Vacancy -> Sources -> Review).
    *   `/outreach/`: Inbox and candidate review queue.
    *   `/admin/`: Global settings, credentials manager, and live pipeline logs.
*   **`backend/app/`**:
    *   `/api/`: FastAPI route definitions.
    *   `/core/`: Configuration (`.env` loading), Database, Celery app init.
    *   `/scrapers/`: Raw data ingestion (Telegram channel parsing, File ingest).
    *   `/scoring/`: The AI brain. `pipeline.py` (TF-IDF pre-filtering) and `gemini.py` (LLM Rubric scoring).
    *   `/tasks/`: Celery asynchronous tasks (`pipeline.py` for sourcing, `reply_pipeline.py` for AI inbox management).
    *   `/outreach/`: Sender logic (Playwright for LinkedIn, Telethon for TG) and the persistent `telegram_listener.py`.
*   **`scripts/`**: Host-level scripts meant to be run manually (e.g., `telegram_login.py`, testing scripts).

---

## 3. Recent Bugs Fixed & Root Causes

1.  **Telegram `database is locked` (SQLite Concurrency):**
    *   **Cause:** Telethon uses SQLite to store session keys. The persistent `run_telegram_listener.py` background process held a continuous write-lock on `sourcer_session.session`. When a Celery worker tried to run `scrape_channels()` using the *same* session file, SQLite rejected it.
    *   **Fix:** Decoupled the sessions. The listener now uses `sourcer_session.session`, while the Celery pipeline scraper explicitly uses a cloned/separate `sourcer_scraper.session`. Updated `telegram_login.py` to accept a `--session scraper|listener` argument to authenticate them independently.
2.  **Next.js CSS / 404 Caching Zombie Bug:**
    *   **Cause:** Stopping the frontend via `Ctrl+C` often left a zombie Next.js process running on port 3000. Relaunching the app caused it to silently boot on port 3001, while the browser still hit port 3000 (which was serving a corrupted `.next` cache, dropping all CSS files).
    *   **Fix:** Enforced a strict `pkill -f "next" && rm -rf frontend/.next` cleanup command prior to clean boots.
3.  **LinkedIn Apify Scraper Returning 0 Results:**
    *   **Cause:** Apify's `harvestapi` was failing silently because it required highly specific Boolean syntax, or it was hitting LinkedIn login walls without active `li_at` cookies being injected into the actor payload.
    *   **Fix:** Deprecated and completely removed the Apify LinkedIn search block from `pipeline.py` and the UI. Redirected the workflow to rely on manual Sales Navigator XLSX exports via the `file_ingest.py` path.

---

## 4. UI/UX & Model-Specific Changes (Gemini vs. Sonnet)

*   **Sonnet's Contributions (Early Phases):** Primarily handled the heavy lifting of the initial backend architecture, Supabase schema design, Celery orchestration, and the foundational React components.
*   **Gemini/Antigravity's Contributions (Late Phases):**
    *   **Dynamic Prompt Refactoring:** Removed all hardcoded "iGaming/Facebook" bias from `gemini.py`. The system prompt (`PLAN_SYSTEM` and `SCORE_SYSTEM`) and scoring rubric are now dynamically generated based on the user's runtime Vacancy inputs (Title, Budget, Geo, Skills).
    *   **Admin Dashboard:** Built `/admin/logs` for real-time Celery pipeline tracking, and `/admin/credentials` for hot-swapping API keys and cookies without restarting the `.env`.
    *   **UI Consolidation:** Updated the Campaign Wizard to reflect the removal of automated LinkedIn scraping, emphasizing the XLSX upload route.

---

## 5. Fragile Areas & Breaking Points

*   **Telethon Session Invalidation:** Telegram's anti-spam system is highly aggressive against API logins via scripts. Attempting to authenticate a brand new API ID (`my.telegram.org`) to a new phone number via the terminal frequently results in a silent shadowban where the login code is never sent. *Warning: Always keep the official Telegram app open when running `telegram_login.py`.*
*   **Playwright LinkedIn Outreach (`linkedin_playwright.py`):** Highly fragile. It relies on DOM selectors for the LinkedIn messaging interface which change frequently. It also relies on the `li_at` cookie being perfectly fresh. If the cookie expires, the Playwright script will crash or timeout.
*   **Celery Zombie Workers:** The `launch.sh` script spins up multiple background processes. If they are not killed cleanly (`kill -9`), Celery workers can hang onto old code versions in memory, causing baffling debugging loops.

---

## 6. Complex Algorithms & Hidden Dependencies

*   **Two-Stage Scoring (`app/scoring/pipeline.py`):** To save LLM costs, the pipeline does *not* send all scraped candidates to Gemini. It first runs a **TF-IDF Embedding Filter** (`stage1_embed_filter`). It vectorizes the candidate's bio and the job description, compares cosine similarity, and brutally drops the bottom 30%. *Warning: If the embedding model (`GEMINI_EMBED_MODEL`) fails, it falls back to passing 100% of candidates to the LLM, causing a massive API bill.*
*   **Hidden Regex Filters:** Inside the scrapers (`linkedin_apify.py`, `telegram.py`), there are hidden Regex heuristics (e.g., `detect_open_to_work()`, `extract_contacts()`). These parse raw text blobs to find emails, phone numbers, and "Open to work" signals before the AI even sees the candidate.

---

## 7. Package Versions & Environment Tweaks

*   **`.env` File Normalization:** Removed spaces from `TELEGRAM_PHONE` formats to ensure Telethon parses them correctly. 
*   **Redis Dependency:** Celery relies entirely on `redis` running on `localhost:6379`. If Homebrew's redis service drops, the entire backend (scrapers, scoring) will queue tasks into the void indefinitely.
*   **Dependencies:** Uses `telethon` (async SQLite caveats applied), `playwright` (requires `playwright install` on host), `supabase-py` (REST client, not the Postgres direct connection), and `google-genai` / `httpx` for OpenRouter routing.

---

## 8. Unimplemented Features & Technical Shortcuts

*   **Phase 3 (AI Reply Handling):** The `run_telegram_listener.py` successfully ingests incoming DMs and updates the database status to `replied`, but the Celery task `process_incoming_reply` (which reads the reply and uses AI to generate a response or categorize intent) is currently a mocked/unimplemented stub.
*   **LinkedIn Search Deprecation:** As a shortcut to stabilize the pipeline, automated LinkedIn scraping was removed. The current AI "Plan" phase still generates Boolean queries for LinkedIn, but they are only useful for manual copying into Sales Navigator.
*   **UI Pagination & Performance:** The `/admin/logs` and `/outreach/inbox` endpoints fetch data without robust pagination. As the database grows, these endpoints will slow down the frontend significantly.
*   **Playwright Headless Toggle:** Playwright is currently hardcoded or relying on `.env` `LI_HEADLESS`. For a server deployment (Docker), it must be strictly headless, but debugging locally often requires setting it to `False` to solve captchas manually.
