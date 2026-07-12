-- Migration: add geo_exclude and sources columns to jobs
-- Run this in the Supabase SQL editor ONCE.

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS geo_exclude text[] DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS sources text[] DEFAULT '{linkedin,telegram}';

-- Index for sources-based queries (optional, useful if filtering by source)
CREATE INDEX IF NOT EXISTS jobs_sources_idx ON public.jobs USING GIN (sources);
