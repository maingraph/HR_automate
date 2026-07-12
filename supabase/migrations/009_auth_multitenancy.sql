-- Tier-1: Auth + Multi-Tenancy (Custom JWT + org_id scoping)
-- Run this in the Supabase SQL editor after existing migrations.

-- === Organizations ===
create table if not exists public.orgs (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    created_at timestamptz not null default now()
);

-- === Users ===
create table if not exists public.users (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references public.orgs(id) on delete cascade,
    email text not null unique,
    password_hash text not null,
    role text not null default 'member', -- owner | member | platform_admin
    created_at timestamptz not null default now()
);

create index if not exists users_org_id_idx on public.users(org_id);
create index if not exists users_email_idx on public.users(email);

-- === Add org_id to all data tables ===

-- Jobs
alter table public.jobs add column if not exists org_id uuid references public.orgs(id) on delete cascade;
create index if not exists jobs_org_id_idx on public.jobs(org_id);

-- Candidates (denormalized org_id for flat filtering)
alter table public.candidates add column if not exists org_id uuid references public.orgs(id) on delete cascade;
create index if not exists candidates_org_id_job_id_idx on public.candidates(org_id, job_id);

-- Pipeline runs
alter table public.pipeline_runs add column if not exists org_id uuid references public.orgs(id) on delete cascade;
create index if not exists pipeline_runs_org_id_job_id_idx on public.pipeline_runs(org_id, job_id);

-- Outreach campaigns
alter table public.outreach_campaigns add column if not exists org_id uuid references public.orgs(id) on delete cascade;
create index if not exists outreach_campaigns_org_id_idx on public.outreach_campaigns(org_id);

-- Outreach leads (denormalized org_id)
alter table public.outreach_leads add column if not exists org_id uuid references public.orgs(id) on delete cascade;
create index if not exists outreach_leads_org_id_campaign_id_idx on public.outreach_leads(org_id, campaign_id);

-- Outreach messages (denormalized org_id)
alter table public.outreach_messages add column if not exists org_id uuid references public.orgs(id) on delete cascade;
create index if not exists outreach_messages_org_id_lead_id_idx on public.outreach_messages(org_id, lead_id);

-- === Backfill: Create Default Org and assign all existing rows ===

-- Insert Default Org (idempotent)
insert into public.orgs (id, name)
values ('00000000-0000-0000-0000-000000000001', 'Default Org')
on conflict (id) do nothing;

-- Backfill org_id on all existing rows
update public.jobs set org_id = '00000000-0000-0000-0000-000000000001' where org_id is null;
update public.candidates set org_id = '00000000-0000-0000-0000-000000000001' where org_id is null;
update public.pipeline_runs set org_id = '00000000-0000-0000-0000-000000000001' where org_id is null;
update public.outreach_campaigns set org_id = '00000000-0000-0000-0000-000000000001' where org_id is null;
update public.outreach_leads set org_id = '00000000-0000-0000-0000-000000000001' where org_id is null;
update public.outreach_messages set org_id = '00000000-0000-0000-0000-000000000001' where org_id is null;

-- Optional: Make org_id NOT NULL after backfill (uncomment if desired)
-- alter table public.jobs alter column org_id set not null;
-- alter table public.candidates alter column org_id set not null;
-- alter table public.pipeline_runs alter column org_id set not null;
-- alter table public.outreach_campaigns alter column org_id set not null;
-- alter table public.outreach_leads alter column org_id set not null;
-- alter table public.outreach_messages alter column org_id set not null;

-- Service backend is sole database entry point. Enforce tenant column presence.
alter table public.jobs alter column org_id set not null;
alter table public.candidates alter column org_id set not null;
alter table public.pipeline_runs alter column org_id set not null;
alter table public.outreach_campaigns alter column org_id set not null;
alter table public.outreach_leads alter column org_id set not null;
alter table public.outreach_messages alter column org_id set not null;

-- No public policies: service-role backend bypasses RLS, anon clients see nothing.
alter table public.orgs enable row level security;
alter table public.users enable row level security;
alter table public.jobs enable row level security;
alter table public.candidates enable row level security;
alter table public.pipeline_runs enable row level security;
alter table public.outreach_campaigns enable row level security;
alter table public.outreach_leads enable row level security;
alter table public.outreach_messages enable row level security;

-- === Seed platform admin user ===
-- Do NOT hardcode a password hash here (must match passlib's bcrypt output).
-- After running this migration, create the first admin with a real hash:
--   cd backend && .venv/bin/python ../scripts/create_admin.py admin@sourcer.local 'YourStrongPassword'
-- That script attaches the user to the Default Org as platform_admin.
