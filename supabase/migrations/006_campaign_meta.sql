-- Add tg_account and qualification_note to outreach_campaigns
-- Run in Supabase SQL editor

ALTER TABLE public.outreach_campaigns
  ADD COLUMN IF NOT EXISTS tg_account       text,
  ADD COLUMN IF NOT EXISTS qualification_note text;
