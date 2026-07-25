import { getAuthHeaders } from "./auth";

export const API = process.env.NEXT_PUBLIC_API_URL || "/api";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text}`);
  }
  return res.json();
}

// ── Campaigns ─────────────────────────────────────────────────────────────

export const getCampaigns = () =>
  apiFetch<Campaign[]>("/outreach/campaigns");

export const getCampaign = (id: string) =>
  apiFetch<Campaign>(`/outreach/campaigns/${id}`);

export const createCampaign = (body: Partial<Campaign>) =>
  apiFetch<Campaign>("/outreach/campaigns", { method: "POST", body: JSON.stringify(body) });

export const updateCampaign = (id: string, body: { name?: string; status?: string }) =>
  apiFetch<Campaign>(`/outreach/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteCampaign = (id: string) =>
  apiFetch<{ deleted: string }>(`/outreach/campaigns/${id}`, { method: "DELETE" });

export const setCampaignMode = (id: string, mode: "copilot" | "autopilot") =>
  apiFetch<{ campaign_id: string; outreach_mode: string }>(
    `/outreach/campaigns/${id}/mode`,
    { method: "PATCH", body: JSON.stringify({ outreach_mode: mode }) }
  );

// ── Leads / Needs Review ──────────────────────────────────────────────────

export const deleteLead = (id: string) =>
  apiFetch<{ deleted: string }>(`/outreach/leads/${id}`, { method: "DELETE" });

export const getNeedsReview = (campaignId: string) =>
  apiFetch<Lead[]>(`/outreach/campaigns/${campaignId}/needs-review`);

export const approveDraft = (leadId: string, text?: string, channel?: string) =>
  apiFetch<{ success: boolean }>(`/outreach/leads/${leadId}/approve-draft`, {
    method: "POST",
    body: JSON.stringify({ text, channel }),
  });

export const rejectDraft = (leadId: string) =>
  apiFetch<{ draft_rejected: boolean }>(`/outreach/leads/${leadId}/reject-draft`, {
    method: "POST",
  });

// ── Conversations ─────────────────────────────────────────────────────────

export const getInbox = () =>
  apiFetch<Lead[]>("/outreach/inbox");  // backed by GET /outreach/inbox

export const getThread = (leadId: string) =>
  apiFetch<Message[]>(`/outreach/conversations/${leadId}/messages`);

export const sendReply = (leadId: string, text: string, channel: string) =>
  apiFetch<{ success: boolean }>(`/outreach/conversations/${leadId}/reply`, {
    method: "POST",
    body: JSON.stringify({ text, channel }),
  });

// ── Shared types ──────────────────────────────────────────────────────────

export type Campaign = {
  id: string;
  name: string;
  job_id?: string;
  tg_template?: string;
  li_template?: string;
  screening_questions?: string[];
  tg_account?: string;
  qualification_note?: string;
  outreach_mode?: "copilot" | "autopilot";
  ai_persona?: string;
  status: string;
  created_at: string;
  updated_at: string;
  total_leads?: number;
  sent_count?: number;
  replied_count?: number;
};

export type Lead = {
  id: string;
  campaign_id: string;
  full_name?: string;
  headline?: string;
  telegram_url?: string;
  linkedin_url?: string;
  preferred_channel?: string;
  status: string;
  ai_intent?: string;
  ai_draft?: string;
  needs_review?: boolean;
  last_message?: string;
  last_message_at?: string;
  unread_count?: number;
  source?: string;
};

export type Message = {
  id: string;
  lead_id: string;
  direction: "sent" | "received";
  channel: string;
  text: string;
  is_auto?: boolean;
  created_at: string;
};
