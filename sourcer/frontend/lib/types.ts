import { ReactNode } from "react";

// ── Form types ────────────────────────────────────────────────────────────────

export type VacancyFormData = {
  title: string;
  description: string;
  skills: string;
  geo: string;
  geo_exclude: string;
  seniority: string;
  budget_min: string | number;
  budget_max: string | number;
  tg_channels: string;
  sources: string[];
};

export type CampaignFormData = {
  name: string;
  jobId: string;
  tgTemplate: string;
  liTemplate: string;
  questions: string[];
  tgAccount: string;
  qualificationNote: string;
};

// ── Component prop types ──────────────────────────────────────────────────────

export type FieldProps = {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
};
