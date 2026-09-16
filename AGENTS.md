# AGENTS.md — Sourcer Engineering Guide

This file is the operating manual for agents working in this repository. Read it before changing code. Keep it current when architecture, workflows, commands, or important project state changes.

## 1. Product purpose

Sourcer is a local-first recruitment workspace. It turns a vacancy into reviewable candidate datasets through independent, observable stages:

```text
Sales Navigator / Telegram / Apollo / file import
                         ↓
                 explicit merge + dedup
                         ↓
          enrichment → rules → similarity → AI grading
                         ↓
              optional outreach workflows
```

Core product principles:

- Every pipeline stage produces a saved, versioned dataset.
- Human review gates separate stages. Do not silently advance the pipeline.
- Draft and partial outputs remain inspectable and exportable.
- Sealed datasets are immutable; editing one creates a child version.
- Source lanes remain independent until explicit merge/dedup.
- Outreach is separate from sourcing and grading.
- Sales Navigator login and filtering remain human-controlled through embedded Chromium.
- Candidate data, credentials, cookies, and generated exports must never enter Git.

This is a strong pilot platform, not yet a fully hardened multi-customer SaaS.

## 2. Source-of-truth order

When documentation disagrees, use this order:

1. Current code and migrations.
2. This `AGENTS.md`.
3. Root `README.md`.
4. `.env.example` and active Compose files.
5. `docs/history/` only for historical context.

Most files under `docs/history/` describe older architecture from April 2026. Do not implement against them without checking current code.

## 3. Repository map

| Path | Responsibility |
| --- | --- |
| `backend/app/main.py` | FastAPI application and router registration |
| `backend/app/api/` | HTTP and WebSocket endpoints |
| `backend/app/core/` | Configuration, auth, database, Redis, Celery, logging |
| `backend/app/services/` | Dataset, job, stage, dedup, and control business rules |
| `backend/app/tasks/` | Celery stage execution and legacy task orchestration |
| `backend/app/scrapers/` | SalesNav, LinkedIn, Telegram, Apollo, and file adapters |
| `backend/app/scoring/` | Gemini/OpenRouter planning, embeddings, and grading |
| `backend/app/outreach/` | Message composition, sending, inbox polling, reply classification |
| `backend/app/schemas/` | Pydantic request/response contracts |
| `backend/tests/` | Primary backend test suite |
| `frontend/app/` | Next.js App Router pages |
| `frontend/components/workflow/WorkflowWorkspace.tsx` | Main pipeline workspace; large and high-risk |
| `frontend/lib/` | API client, types, pipeline presentation, workflow helpers |
| `browser-agent/` | Visible persistent Chromium, Xvfb, noVNC, container entrypoint |
| `supabase/migrations/` | Ordered database schema; current latest is `010_modular_pipeline.sql` |
| `deploy/local/` | Local PostgreSQL/PostgREST compatibility stack |
| `deploy/web/` | Single-address web gateway |
| `scripts/` | Setup, migration, test, and operator tools |
| `data/demo/` | Only intentional tracked demo datasets |
| `outputs/`, `data/uploads/` | Generated/local data; never commit |
| `archive/` | Pre-consolidation tools retained for reference and feature-parity checks |
| `design/` | Tracked UI design references |
| `docs/history/` | Historical reports; not current operational truth |

Do not restore archived tools into runtime paths without proving current implementation lacks required behavior.

## 4. Runtime architecture

### Backend

- Python 3.11
- FastAPI + Uvicorn
- Celery worker and Celery Beat
- Redis broker, result backend, and pub/sub
- PostgreSQL through Supabase-compatible PostgREST APIs
- Pydantic v2
- Gemini through `google-genai`; OpenRouter fallback
- Telethon for Telegram
- Playwright for browser automation

### Frontend

- Next.js 15
- React 18
- TypeScript
- Tailwind CSS
- `react-window` for large candidate lists

### Browser agent

Browser agent owns a persistent Chromium profile in Docker volume `browser_profile`.

- Chromium is visible through Xvfb/noVNC.
- Login is manual.
- Cookies persist across normal container rebuilds.
- API controls browser through authenticated internal endpoints.
- Automation must yield to manual control and preserve locked search URL.
- Do not delete browser volume or profile to fix ordinary session errors.
- Stale `SingletonLock`, `SingletonCookie`, and `SingletonSocket` files may be removed; cookies and profile data may not.

### Database modes

- Default: `SOURCER_DATABASE_MODE=local`.
- Local mode layers `docker-compose.local.yml` over `docker-compose.yml`.
- External mode uses configured Supabase values and skips local database layer.
- Web mode additionally layers `docker-compose.web.yml`.
- Overlay Compose files are not standalone projects.

Ordered migrations are applied from `supabase/migrations/`. Never edit an already-applied migration for a new schema change. Add next numbered migration.

## 5. Pipeline model and invariants

Current stage types:

```text
salesnav_extract
telegram_extract
apollo_extract
file_import
merge_dedup
profile_enrich
rules_filter
similarity_analyze
ai_grade
```

Canonical definitions:

- `backend/app/services/stages.py`
- `backend/app/schemas/workflow.py`
- `backend/app/tasks/workflow.py`

Stage status transitions are validated. Never update status directly when `transition_stage()` applies.

Current lifecycle:

```text
pending
  → running
  → pause_requested → paused → running
  → awaiting_auth → running
  → awaiting_user → running/completed/skipped
  → completed/stopped/failed
```

Terminal states must not transition again.

Dataset states:

```text
draft | sealed | partial | failed
```

Dataset invariants:

- Non-source stages require at least one input dataset.
- Inputs must be `sealed` or `partial`.
- Required capability for downstream stages currently includes `normalized`.
- Candidate identity is enforced per dataset through `candidate_key`.
- Writes are organization-scoped.
- Editing sealed data must fork through dataset service.
- Lineage belongs in `parent_ids` and metadata.
- Import/export formats are XLSX, CSV, and lossless JSON.
- Never mutate sealed records directly in database or endpoint code.

## 6. Authentication and tenancy

- JWT auth and organization isolation are active.
- Every job, stage, dataset, candidate record, browser session, and outreach operation must be scoped by `org_id`.
- API additions must use current-user dependency unless intentionally public.
- Never trust client-provided organization identifiers.
- Unknown users must receive authentication errors, not internal server errors.
- Registration is controlled by `ALLOW_REGISTRATION`.
- Disable public registration after pilot accounts are created.

Any database query touching tenant data must include `org_id`. Missing scope is a release-blocking security bug.

## 7. Sales Navigator rules

Sales Navigator is highest-risk subsystem because LinkedIn UI changes, virtualized lists, throttling, and manual browser control interact.

Before changing it, inspect:

- `backend/app/scrapers/linkedin_salesnav.py`
- `backend/app/scrapers/salesnav_selectors.py`
- `backend/app/scrapers/salesnav_card_extractor.py`
- `backend/app/scrapers/salesnav_sidebar_extractor.py`
- `backend/app/scrapers/salesnav_semantic_sections.py`
- `backend/app/browser_agent/main.py`
- `backend/app/tasks/workflow.py`
- `backend/tests/test_salesnav_pagination.py`

Required behavior:

- Accept only LinkedIn Sales Navigator people-search URLs.
- Preserve user-reviewed `locked_search_url`.
- Fresh reruns start from locked URL, not last visible results page.
- Scope selectors to actual result pane; generic `li` selectors are unsafe.
- Expect virtualized cards to mount/unmount while scrolling.
- Match opened drawer to exact candidate before reading details.
- Wait for result/page identity changes, not `networkidle`.
- Return browser to locked people search after profile-link extraction.
- Keep public LinkedIn URL separate from SalesNav lead URL.
- Preserve raw visible sections when structured parsing is uncertain.
- Never replace rich existing fields with empty or lower-quality fallback values.
- Treat “View all skills,” relationship text, feed text, dates, and mutual connections as contamination, not candidate fields.
- Detect LinkedIn rate-limit/error panels and pause safely.
- Do not export error panels as candidate data.
- Use conservative pacing. Do not launch repeated live batches to test small code changes.
- Avoid state-changing LinkedIn controls such as Save, Message, Ask intro, or Add contact info during extraction tests.

Live LinkedIn tests must be bounded: one profile first, then one page, then full batch only after field-quality validation.

## 8. Adding or changing features safely

### Backend/API change

1. Find closest route, service, schema, task, and test.
2. Keep HTTP parsing in `api/`; put business rules in `services/`.
3. Put long-running work in Celery tasks.
4. Update Pydantic contracts and frontend types together.
5. Add organization scope to every data operation.
6. Preserve stage transition and dataset immutability rules.
7. Add focused tests before broad integration tests.

### New pipeline stage

Update all relevant layers:

1. `StageType` in `backend/app/schemas/workflow.py`.
2. `STAGE_TYPES`, transitions/capabilities in `backend/app/services/stages.py`.
3. Executor dispatch in `backend/app/tasks/workflow.py`.
4. Dataset kind, capabilities, lineage, checkpoint behavior.
5. API validation where stage-specific config exists.
6. Frontend TypeScript types and API client.
7. Pipeline presentation and controls.
8. WebSocket/progress events.
9. Tests for creation, invalid inputs, transitions, pause/stop, output, and rerun.
10. This file’s stage list and architecture notes.

### Database change

1. Create next ordered migration; never rewrite old migration history.
2. Include tenant indexes and foreign keys where appropriate.
3. Confirm local PostgREST compatibility.
4. Test clean database initialization and existing database migration.
5. Update `.env.example`, README, and this file if operational behavior changes.

### Frontend change

- Preserve existing Sourcer dark-purple design language unless user explicitly requests rebrand.
- Keep job workspace source-first and action-oriented.
- Do not collapse independent pipeline lanes into one hidden automatic flow.
- Do not make SalesNav browser cover core controls.
- Maintain loading, error, empty, and partial-result states.
- `WorkflowWorkspace.tsx` is already large. Prefer extracting focused components/helpers instead of adding another large inline block.
- Use server/API truth for stages and datasets; do not invent parallel client state machines.

### Scraper/parser change

- Keep raw source payload.
- Produce normalized fields without discarding source-specific evidence.
- Add deterministic fixtures/tests for parsers.
- Do not claim live correctness from DOM/unit tests alone.
- Validate field coverage and contamination on a small real sample.
- Stop when source throttles or authentication changes.

## 9. Commands

### Configure only

```bash
cp .env.example .env
SOURCER_CONFIG_ONLY=1 bash launch.sh
```

### Run local stack

```bash
bash launch.sh
```

Default endpoints:

- App: `http://localhost:3210`
- API docs: `http://localhost:8210/docs`
- Redis: `127.0.0.1:6389`
- Database: `127.0.0.1:55422`
- Embedded browser: inside job workspace

### Run single-address web mode

```bash
SOURCER_WEB_MODE=1 bash launch.sh
```

Gateway: `http://localhost:8088`.

### Compose inspection

Local database mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml ps
docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f
```

Web mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml -f docker-compose.web.yml ps
```

### Backend tests

```bash
cd backend
python -m pip install -r requirements.txt
pytest
```

Run focused tests while iterating:

```bash
cd backend
pytest tests/test_workflow_transitions.py
pytest tests/test_dataset_interchange.py
pytest tests/test_salesnav_pagination.py
pytest tests/test_linkedin_public_profile.py
```

### Frontend

```bash
cd frontend
npm ci
npm run build
```

`npm run lint` uses Next lint command and may require version-specific maintenance; production build is required verification.

### Browser image

```bash
docker build -f browser-agent/Dockerfile .
```

### Migration checks

```bash
python scripts/check_migration.py
python scripts/apply_schema.py
```

Use `apply_schema.py` only for configured external Supabase mode. Local mode applies ordered migrations during initial database creation.

## 10. Verification matrix

Run verification proportional to change:

| Change | Minimum verification |
| --- | --- |
| Backend utility/parser | Focused pytest + Python compile/import |
| API/service/schema | Focused tests + workflow transition tests |
| Dataset behavior | Dataset interchange + workflow tests |
| Frontend-only | `npm run build` |
| Cross-stack contract | Backend tests + frontend build |
| Browser agent | Focused parser tests + Docker build + health endpoint |
| SalesNav behavior | Tests + one-profile live check + field-quality review |
| Compose/runtime | `docker compose config` with correct overlays + service health |
| Migration | Clean init + upgrade path |
| Auth/tenancy | Positive access test + cross-org denial test |

Before handoff:

```bash
git diff --check
git status --short
```

Report tests actually run. Never describe an unrun check as passing.

## 11. Security and data handling

Never commit or print:

- `.env` values
- JWT secrets
- Supabase keys
- Gemini/OpenRouter/Apify/Telegram credentials
- LinkedIn passwords or `li_at` cookies
- Telethon `.session` files
- Browser profile/cookies
- Candidate exports or uploaded CVs
- Real candidate PII in test fixtures

Use `.env.example` placeholders only.

Generated candidate files belong under ignored `outputs/` or `data/`. Tests must use synthetic people and organizations.

Do not expose:

- Redis
- PostgreSQL
- browser-agent control API
- noVNC without gateway authentication

Web gateway binding to `0.0.0.0` exposes it to local network. Treat any such change as security-sensitive and state intended exposure explicitly.

LinkedIn and Telegram automation may be constrained by platform terms, account restrictions, privacy law, and data-retention requirements. Preserve human control, rate limits, auditability, and deletion paths.

## 12. Git and concurrent-work rules

- Branch default is `main`; repository remote is `maingraph/HR_automate`.
- Preserve user and other-agent changes.
- Inspect `git status` and active tasks before editing.
- Do not reset, revert, or overwrite unrelated dirty files.
- Avoid editing files another task is actively changing.
- Keep commits scoped by purpose.
- Do not commit `outputs/`, screenshots, credentials, sessions, caches, or local database state.
- Do not commit until requested or normal task workflow explicitly includes Git delivery.

When repository is dirty:

1. Identify which files belong to current task.
2. Read existing diff before changing overlapping files.
3. Patch minimally.
4. Verify combined result, not only new lines.
5. Tell user which pre-existing changes were preserved.

## 13. Current project state — update this section

Snapshot date: 2026-09-16.

Stable baseline:

- Root project consolidated and pushed.
- `main` tracks `origin/main`.
- Modular nine-stage pipeline exists.
- Local and external database modes exist.
- Authentication and organization isolation exist.
- Local full stack and single-address web mode run through Docker Compose.
- SalesNav URL can be edited, opened, reviewed, locked, and extracted.
- Telegram discovery/extraction and dataset import/export exist.
- SalesNav pagination and virtual-list hardening, exact card/drawer matching,
  semantic experience/education/skills parsing, public LinkedIn-profile
  enrichment fallback, rate-limit detection with safe pause, Chromium
  stale-lock recovery, field contamination cleanup, and seniority/experience
  derivation were completed during the verified 63-profile Media Buyer batch
  and committed on 2026-09-16.
- Verified enriched workbook for that batch lives under
  `outputs/salesnav_public_enriched_63_20260729/` (63/63 URLs, 291 roles,
  74 education entries, 392 skills, 49 languages; `outputs/` stays untracked).
- Planned next feature wave: the 2026-08-20 LinkedIn Boolean-search lane and
  continuous-outreach expansion — see `docs/EXPANSION_PLAN_2026-08-20.md`.
  Not implemented yet.

Active uncommitted work at snapshot:

- None; the worktree was committed and pushed on 2026-09-16.

Known gaps:

- The 2026-09-16 commit wave received syntax checks, manual diff review, and
  the live validation already performed during the 63-profile batch, but not
  a fresh full `pytest` pass (no local venv at commit time).
- Production hosting, backups, monitoring, retention/deletion policy, and recruiter acceptance testing remain unfinished.
- Historical docs need reconciliation with current architecture.
- Large `WorkflowWorkspace.tsx` should be decomposed during future feature work.

Remove completed work from “Active uncommitted work,” record durable outcome under “Stable baseline,” and keep unresolved items under “Known gaps.”

## 14. How agents must maintain this file

Update `AGENTS.md` in same change when any of these occur:

- New or removed top-level component.
- New pipeline stage or dataset state.
- Changed stage transition, capability, or lineage rule.
- New database mode, migration process, or deployment mode.
- Changed build/test command.
- Auth, tenancy, secret, or networking change.
- Major source-adapter behavior change.
- Important work moves from active to stable.
- New known risk affects future implementation.

Maintenance rules:

- Keep durable architecture above volatile status.
- Date current-state snapshot.
- Replace stale statements; do not append endless changelog entries.
- Link behavior to canonical files.
- Never add secrets, candidate data, temporary tunnel URLs, or personal credentials.
- Keep historical narrative in `docs/history/`, not here.
- After editing, verify commands and paths still exist.
- If code and this file disagree, fix this file in same task unless code itself is wrong.

## 15. Definition of done

Feature is done only when:

- User-visible behavior matches request.
- Architecture and invariants remain intact.
- Tenant boundaries are enforced.
- Partial/error/auth/rate-limit paths are handled.
- Tests and builds appropriate to change pass.
- Runtime/deployment configuration is updated when required.
- README, `.env.example`, migrations, and this file are updated when affected.
- No secrets or generated candidate data enter Git.
- Handoff states what changed, what was verified, and what remains uncertain.
