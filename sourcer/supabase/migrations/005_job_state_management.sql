-- Add pause/resume support to jobs
-- Migration: 005_job_state_management.sql
-- Created: 2026-04-28

-- Add paused status and checkpoint tracking
ALTER TABLE public.jobs 
ADD COLUMN IF NOT EXISTS paused_at timestamptz,
ADD COLUMN IF NOT EXISTS checkpoint jsonb DEFAULT '{}'::jsonb;

-- Update status enum to include 'paused'
-- Note: Jobs can be in 'paused' status to indicate user-initiated pause

-- Checkpoint structure:
-- {
--   "stage": "embed",           -- Last completed stage
--   "candidates_count": 150,    -- Progress so far
--   "can_resume": true          -- Whether resume is safe
-- }

COMMENT ON COLUMN public.jobs.paused_at IS 'Timestamp when job was paused by user';
COMMENT ON COLUMN public.jobs.checkpoint IS 'Pipeline state for resume functionality';
