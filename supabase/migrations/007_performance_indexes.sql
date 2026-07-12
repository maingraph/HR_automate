-- Performance optimization indexes for Phase 3C
-- Created: 2026-04-27

-- Candidates table optimizations
-- Index for filtering by status (used in many queries)
create index if not exists candidates_status_idx on public.candidates(job_id, status);

-- Index for filtering by open_to_work
create index if not exists candidates_otw_idx on public.candidates(job_id, open_to_work) where open_to_work = true;

-- Index for scan_depth filtering (Phase 1 vs Phase 2)
create index if not exists candidates_scan_depth_idx on public.candidates(job_id, scan_depth);

-- Composite index for common query pattern: job_id + status + score
create index if not exists candidates_job_status_score_idx on public.candidates(job_id, status, gemini_score desc nulls last);

-- Index for updated_at (used for sorting recent updates)
create index if not exists candidates_updated_at_idx on public.candidates(job_id, updated_at desc);

-- Pipeline runs optimizations
-- Index for sorting by started_at (used in admin logs)
create index if not exists pipeline_runs_started_at_idx on public.pipeline_runs(started_at desc);

-- Composite index for job_id + stage queries
create index if not exists pipeline_runs_job_stage_idx on public.pipeline_runs(job_id, stage, started_at desc);

-- Jobs table optimization
-- Index for created_at (used for listing recent jobs)
create index if not exists jobs_created_at_idx on public.jobs(created_at desc);

-- Index for updated_at
create index if not exists jobs_updated_at_idx on public.jobs(updated_at desc);
