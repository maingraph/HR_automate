# Sourcer

Local, observable recruitment workspace. Run sourcing, merging, enrichment, filtering, and grading as independent tools or assemble them into a gated pipeline.

## Pipeline

```text
Sales Navigator / Telegram / Apollo / file import
                    ↓
          explicit merge + dedup
                    ↓
        enrichment → rules → similarity
                    ↓
                AI grading
```

Every stage creates a versioned dataset. Outputs pause at a gate where they can be inspected, edited, exported, replaced through import, sealed, or passed into another stage. Partial and stopped runs remain exportable.

## Interactive Sales Navigator

Sourcer runs persistent Chromium in a dedicated browser-agent container and renders it in the job workspace through noVNC. Login is manual. Browser cookies stay inside a local Docker volume; LinkedIn passwords are never stored by Sourcer.

Workflow:

1. Start browser.
2. Open AI-generated search.
3. Log in or approve LinkedIn challenge if requested.
4. Adjust Sales Navigator filters directly.
5. Lock search.
6. Start Sales Navigator stage.
7. Pause safely, take manual control, resume, or hard-stop while keeping completed records.

## Quick start

Requirements: Docker Desktop and configured `.env`. A private local database is
included, so a Supabase account is optional.

```bash
cp .env.example .env
# Configure JWT, AI, and optional source credentials.
bash launch.sh
```

Open:

- App: `http://localhost:3210`
- API: `http://localhost:8210/docs`
- Embedded browser: inside each job workspace

Generate a local browser-agent token before starting:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put result in `BROWSER_AGENT_TOKEN` inside `.env`.

`launch.sh` generates a private noVNC password in `.env` when one is missing.
The viewer asks for this password before showing the persistent Chromium session.

### Single web address

The web profile puts the frontend, API, WebSocket events, and password-protected
browser viewer behind one localhost address:

```bash
SOURCER_WEB_MODE=1 bash launch.sh
```

Open `http://localhost:8088`. For a temporary HTTPS pilot from the same Mac:

```bash
cloudflared tunnel --url http://localhost:8088
```

The generated `trycloudflare.com` address is temporary and works only while the
Mac, Docker, and tunnel stay running. A permanent pilot should use a small
dedicated server and a named domain.

### Database modes

`SOURCER_DATABASE_MODE=local` is the default. It starts PostgreSQL and PostgREST
privately alongside Sourcer, applies ordered migrations on first launch, and
binds the database only to `127.0.0.1:55422`. The local compatibility schema
omits the unused legacy pgvector column; modular similarity results remain in
versioned dataset records.

To retain an existing Supabase project, set:

```text
SOURCER_DATABASE_MODE=external
```

Then configure the three `SUPABASE_*` values and apply migrations with
`python scripts/apply_schema.py`.

Readiness is available at `http://localhost:8210/health/ready`.

## Components

| Path | Role |
| --- | --- |
| `backend/` | FastAPI API, Celery stages, source adapters, scoring, outreach |
| `frontend/` | Next.js workspace, stage controls, dataset gate, noVNC embed |
| `browser-agent/` | Persistent Chromium, Playwright controller, Xvfb/noVNC |
| `supabase/migrations/` | Ordered database schema and migrations |
| `scripts/` | Setup and operator utilities |
| `archive/` | Pre-consolidation tools retained until parity is verified |

## Dataset interchange

Every dataset supports:

- XLSX: `Candidates` and `Metadata` sheets;
- CSV: nested fields encoded as JSON strings;
- JSON: lossless manifest, lineage, records, and source payloads.

Editing a sealed dataset creates a child version. Existing version remains unchanged.

## Development

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

## Safety

Candidate data contains personal information. Keep deployment local, protect `.env`, restrict Supabase service credentials, and define retention/deletion policy before production use. LinkedIn automation can trigger account restrictions and must follow applicable terms and laws.

Historical architecture notes live under `docs/history/`.
