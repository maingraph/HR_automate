-- Modular pipeline: immutable stage outputs with editable draft datasets.

create table if not exists public.candidate_datasets (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references public.orgs(id) on delete cascade,
    job_id uuid not null references public.jobs(id) on delete cascade,
    name text not null,
    kind text not null,
    schema_version int not null default 1,
    capabilities text[] not null default '{}',
    parent_ids uuid[] not null default '{}',
    state text not null default 'draft'
        check (state in ('draft', 'sealed', 'partial', 'failed')),
    row_count int not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    sealed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.candidate_records (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references public.orgs(id) on delete cascade,
    dataset_id uuid not null references public.candidate_datasets(id) on delete cascade,
    candidate_key text not null,
    payload jsonb not null default '{}'::jsonb,
    source_payload jsonb not null default '{}'::jsonb,
    tags text[] not null default '{}',
    included boolean not null default true,
    position int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(dataset_id, candidate_key)
);

create table if not exists public.stage_runs (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references public.orgs(id) on delete cascade,
    job_id uuid not null references public.jobs(id) on delete cascade,
    stage_type text not null check (stage_type in (
        'salesnav_extract', 'telegram_extract', 'apollo_extract', 'file_import',
        'merge_dedup', 'profile_enrich', 'rules_filter',
        'similarity_analyze', 'ai_grade'
    )),
    status text not null default 'pending' check (status in (
        'pending', 'running', 'pause_requested', 'paused', 'awaiting_user',
        'awaiting_auth', 'completed', 'stopped', 'failed', 'skipped'
    )),
    input_dataset_ids uuid[] not null default '{}',
    output_dataset_id uuid references public.candidate_datasets(id) on delete set null,
    config jsonb not null default '{}'::jsonb,
    progress jsonb not null default '{"current":0,"total":0}'::jsonb,
    checkpoint jsonb not null default '{}'::jsonb,
    error text,
    attempt int not null default 1,
    idempotency_key text,
    celery_task_id text,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(job_id, idempotency_key)
);

create table if not exists public.browser_sessions (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references public.orgs(id) on delete cascade,
    job_id uuid not null references public.jobs(id) on delete cascade,
    state text not null default 'stopped' check (state in (
        'starting', 'ready', 'awaiting_auth', 'manual_control',
        'automating', 'paused', 'stopped', 'failed'
    )),
    current_url text,
    locked_search_url text,
    automation_state jsonb not null default '{}'::jsonb,
    viewer_url text,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(job_id)
);

create index if not exists candidate_datasets_job_idx
    on public.candidate_datasets(org_id, job_id, created_at desc);
create index if not exists candidate_records_dataset_idx
    on public.candidate_records(dataset_id, position);
create index if not exists candidate_records_payload_idx
    on public.candidate_records using gin(payload);
create index if not exists stage_runs_job_idx
    on public.stage_runs(org_id, job_id, created_at desc);

alter table public.candidate_datasets enable row level security;
alter table public.candidate_records enable row level security;
alter table public.stage_runs enable row level security;
alter table public.browser_sessions enable row level security;

drop trigger if exists candidate_datasets_touch on public.candidate_datasets;
create trigger candidate_datasets_touch before update on public.candidate_datasets
    for each row execute function public.touch_updated_at();
drop trigger if exists candidate_records_touch on public.candidate_records;
create trigger candidate_records_touch before update on public.candidate_records
    for each row execute function public.touch_updated_at();
drop trigger if exists stage_runs_touch on public.stage_runs;
create trigger stage_runs_touch before update on public.stage_runs
    for each row execute function public.touch_updated_at();
drop trigger if exists browser_sessions_touch on public.browser_sessions;
create trigger browser_sessions_touch before update on public.browser_sessions
    for each row execute function public.touch_updated_at();

-- Existing candidate rows become one sealed legacy dataset per job.
do $$
declare
    j record;
    dataset_id uuid;
begin
    for j in
        select jobs.id, jobs.org_id, jobs.title
        from public.jobs
        where jobs.org_id is not null
          and exists (select 1 from public.candidates c where c.job_id = jobs.id)
          and not exists (
              select 1 from public.candidate_datasets d
              where d.job_id = jobs.id and d.kind = 'legacy'
          )
    loop
        insert into public.candidate_datasets (
            org_id, job_id, name, kind, capabilities, state, row_count, sealed_at
        )
        values (
            j.org_id, j.id, j.title || ' — legacy candidates', 'legacy',
            array['normalized', 'legacy'], 'sealed',
            (select count(*) from public.candidates c where c.job_id = j.id), now()
        ) returning id into dataset_id;

        insert into public.candidate_records (
            org_id, dataset_id, candidate_key, payload, source_payload, position
        )
        select
            j.org_id,
            dataset_id,
            coalesce(c.dedup_key, c.id::text),
            to_jsonb(c) - 'embedding' - 'raw',
            coalesce(c.raw, '{}'::jsonb),
            row_number() over (order by c.created_at, c.id)::int
        from public.candidates c
        where c.job_id = j.id;
    end loop;
end $$;
