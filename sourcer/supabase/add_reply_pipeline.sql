-- Phase 3: Copilot / Autopilot pipeline columns
-- Run in Supabase SQL editor AFTER outreach_schema.sql

-- === outreach_campaigns: add outreach_mode ===
-- outreach_mode: 'copilot' (default) | 'autopilot'
--   copilot   → AI drafts a reply, human approves before sending
--   autopilot → AI sends immediately, only alerts on qualified/human-handoff intent
ALTER TABLE public.outreach_campaigns
  ADD COLUMN IF NOT EXISTS outreach_mode text NOT NULL DEFAULT 'copilot',
  ADD COLUMN IF NOT EXISTS ai_persona    text;   -- optional system-prompt persona for this campaign
                                                  -- e.g. "You are Alex, a friendly HR recruiter at TechCorp"

-- === outreach_leads: add AI reply state columns ===
ALTER TABLE public.outreach_leads
  ADD COLUMN IF NOT EXISTS ai_intent    text,    -- classified intent: interested | questions | declined | other
  ADD COLUMN IF NOT EXISTS ai_draft     text,    -- the LLM-generated draft reply (copilot holds it here)
  ADD COLUMN IF NOT EXISTS needs_review boolean NOT NULL DEFAULT false; -- true = copilot draft awaiting approval

CREATE INDEX IF NOT EXISTS outreach_leads_needs_review_idx
  ON public.outreach_leads(campaign_id, needs_review)
  WHERE needs_review = true;
