-- Sourcer schema: jobs, candidates, scoring, pgvector embeddings
-- Run this in the Supabase SQL editor.

-- === Extensions ===
create extension if not exists "uuid-ossp";
create extension if not exists vector;

-- === Jobs ===
create table if not exists public.jobs (
    id uuid primary key default uuid_generate_v4(),
    title text not null,
    description text,
    skills text[] default '{}',
    geo text,
    seniority text,
    budget_min int,
    budget_max int,
    tg_channels text[] default '{}',
    linkedin_boolean text,
    tg_keywords text[] default '{}',
    rubric jsonb,
    status text not null default 'draft', -- draft | queued | running | done | error
    error text,
    stats jsonb default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists jobs_status_idx on public.jobs(status);

-- === Candidates ===
create table if not exists public.candidates (
    id uuid primary key default uuid_generate_v4(),
    job_id uuid references public.jobs(id) on delete cascade,
    source text not null, -- linkedin | telegram | file | apollo | hunter
    source_id text,       -- source-native id (url, msg id, etc)

    full_name text,
    first_name text,
    last_name text,
    username text,        -- telegram @handle, linkedin public id
    headline text,
    bio text,
    raw_text text,        -- full scraped blob
    location text,
    geo_normalized text,
    seniority text,
    years_experience numeric,
    skills text[] default '{}',
    languages text[] default '{}',

    linkedin_url text,
    telegram_url text,
    email text,
    phone text,
    other_links jsonb default '[]'::jsonb,

    -- scoring
    embedding vector(768),
    embed_similarity float,
    gemini_score int,
    gemini_reasoning text,
    gemini_dimensions jsonb,   -- {skills: 80, experience: 70, ...}
    red_flags text[] default '{}',
    open_to_work boolean default false,
    otw_signal text,           -- detection source

    enriched jsonb default '{}'::jsonb,
    raw jsonb default '{}'::jsonb, -- original source payload
    dedup_key text,            -- hash of (username|url|email|name)

    status text not null default 'new', -- new | filtered | scored | rejected
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists candidates_job_id_idx on public.candidates(job_id);
create index if not exists candidates_source_idx on public.candidates(source);
create index if not exists candidates_dedup_key_idx on public.candidates(job_id, dedup_key);
create index if not exists candidates_score_idx on public.candidates(job_id, gemini_score desc);
create index if not exists candidates_embedding_idx on public.candidates
    using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- === Pipeline runs (audit) ===
create table if not exists public.pipeline_runs (
    id uuid primary key default uuid_generate_v4(),
    job_id uuid references public.jobs(id) on delete cascade,
    stage text not null, -- query_gen | scrape_linkedin | scrape_telegram | ingest_file | normalize | embed | score
    status text not null, -- started | ok | error
    count int default 0,
    message text,
    started_at timestamptz default now(),
    ended_at timestamptz
);

create index if not exists pipeline_runs_job_idx on public.pipeline_runs(job_id);

-- === Helper: match by cosine similarity ===
create or replace function public.match_candidates(
    target_job_id uuid,
    query_embedding vector(768),
    match_count int default 500
)
returns table (
    id uuid,
    similarity float
)
language sql stable as $$
    select c.id, 1 - (c.embedding <=> query_embedding) as similarity
    from public.candidates c
    where c.job_id = target_job_id and c.embedding is not null
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- === updated_at triggers ===
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists jobs_touch on public.jobs;
create trigger jobs_touch before update on public.jobs
    for each row execute function public.touch_updated_at();

drop trigger if exists candidates_touch on public.candidates;
create trigger candidates_touch before update on public.candidates
    for each row execute function public.touch_updated_at();
