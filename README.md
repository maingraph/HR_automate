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

Requirements: Docker Desktop, Supabase project, and configured `.env`.

```bash
cp .env.example .env
# Configure Supabase, JWT, AI, and optional source credentials.
python scripts/apply_schema.py
docker compose up --build
```

Open:

- App: `http://localhost:3210`
- API: `http://localhost:8210/docs`
- Embedded browser viewer: `http://127.0.0.1:6210/vnc.html`

Generate a local browser-agent token before starting:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put result in `BROWSER_AGENT_TOKEN` inside `.env`.

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
