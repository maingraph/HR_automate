-- Outreach module: campaigns, leads, messages
-- Run this in the Supabase SQL editor after schema.sql.

create table if not exists public.outreach_campaigns (
    id uuid primary key default uuid_generate_v4(),
    job_id uuid references public.jobs(id) on delete set null,
    name text not null,
    tg_template text,
    li_template text,
    screening_questions text[] default '{}',
    status text default 'draft', -- draft | active | paused | done
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists outreach_campaigns_status_idx on public.outreach_campaigns(status);
create index if not exists outreach_campaigns_job_idx on public.outreach_campaigns(job_id);

create table if not exists public.outreach_leads (
    id uuid primary key default uuid_generate_v4(),
    campaign_id uuid references public.outreach_campaigns(id) on delete cascade,
    candidate_id uuid references public.candidates(id) on delete set null,
    full_name text,
    headline text,
    linkedin_url text,
    telegram_url text,
    email text,
    source text, -- linkedin | telegram | file
    score int,
    status text default 'pending', -- pending | sent | replied | qualified | rejected | skipped
    preferred_channel text default 'telegram', -- telegram | linkedin
    last_message text,
    last_message_at timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists outreach_leads_campaign_idx on public.outreach_leads(campaign_id);
create index if not exists outreach_leads_status_idx on public.outreach_leads(status);
create index if not exists outreach_leads_last_msg_idx on public.outreach_leads(last_message_at desc);

create table if not exists public.outreach_messages (
    id uuid primary key default uuid_generate_v4(),
    lead_id uuid references public.outreach_leads(id) on delete cascade,
    direction text not null, -- sent | received
    channel text not null, -- telegram | linkedin
    text text not null,
    is_auto boolean default true,
    created_at timestamptz default now()
);

create index if not exists outreach_messages_lead_idx on public.outreach_messages(lead_id);
create index if not exists outreach_messages_created_idx on public.outreach_messages(created_at desc);
