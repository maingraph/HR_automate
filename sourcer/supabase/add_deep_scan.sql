-- Migration: two-pass scraping support
-- Run ONCE in the Supabase SQL editor.

-- Track which pass each candidate came from
ALTER TABLE public.candidates
  ADD COLUMN IF NOT EXISTS scan_depth   int  DEFAULT 1,          -- 1=Phase1 shallow, 2=Phase2 deep
  ADD COLUMN IF NOT EXISTS educations   jsonb DEFAULT '[]'::jsonb, -- [{schoolName, fieldOfStudy, location, start, end}]
  ADD COLUMN IF NOT EXISTS positions    jsonb DEFAULT '[]'::jsonb; -- [{title, company, location, start, end, desc}]

-- Extended job phases
-- status values: draft | queued | running | phase1_done | running_deep | done | error
-- No schema change needed — status is already a free-text column

CREATE INDEX IF NOT EXISTS candidates_scan_depth_idx ON public.candidates(job_id, scan_depth);
