# Tier-1 Multi-Tenancy Setup

Auth + multi-tenancy layer built. Need 3 manual steps to activate:

## 1. Add JWT_SECRET to .env

Generate secret:
```bash
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))"
```

Add output to `sourcer/.env`.

## 2. Apply migration 006

Run in Supabase SQL Editor:
```bash
cat supabase/migrations/006_auth_multitenancy.sql
```

Creates:
- `orgs` + `users` tables
- `org_id` column on all 6 data tables (jobs, candidates, pipeline_runs, campaigns, leads, messages)
- Default Org + backfill existing rows

## 3. Create first admin user

After migration:
```bash
cd backend
python3 ../scripts/create_admin.py admin@yourcompany.com 'YourStrongPassword'
```

## What's wired

**Backend:**
- ✅ JWT auth (`app/core/auth.py`)
- ✅ `/auth/register`, `/auth/login`, `/auth/me` routes
- ✅ All routes filter by `current.org_id`
- ✅ WebSocket auth verifies org ownership

**Frontend:**
- ✅ Login/register page (`/login`) with Stitch design
- ✅ Token storage in localStorage
- ✅ `Authorization: Bearer` header on all API calls
- ✅ User menu + logout in nav
- ✅ Root page redirects: authenticated → `/dashboard`, else → `/login`

## Test

1. Do steps 1-3 above
2. Start backend: `cd backend && .venv/bin/uvicorn app.main:app --reload`
3. Start frontend: `cd frontend && npm run dev`
4. Visit `http://localhost:3000` → redirects to `/login`
5. Register new org or login with admin
6. Should land on `/dashboard` with nav showing email + logout

## Notes

- Migration 006 is idempotent (safe to re-run)
- Existing data assigned to Default Org (UUID `00000000-0000-0000-0000-000000000001`)
- JWT expires in 7 days (configurable via `JWT_EXPIRE_MINUTES`)
- Credentials (LinkedIn/Telegram/API keys) still global in `.env` — per-tenant creds = Tier-2
