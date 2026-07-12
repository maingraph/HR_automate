import { API, apiFetch } from "./api";
import { getAuthHeaders } from "./auth";

export type StageType =
  | "salesnav_extract" | "telegram_extract" | "apollo_extract" | "file_import"
  | "merge_dedup" | "profile_enrich" | "rules_filter"
  | "similarity_analyze" | "ai_grade";

export type StageRun = {
  id: string;
  job_id: string;
  stage_type: StageType;
  status: string;
  input_dataset_ids: string[];
  output_dataset_id?: string;
  config: Record<string, unknown>;
  progress: { current?: number; total?: number; percentage?: number };
  checkpoint: Record<string, unknown>;
  error?: string;
  attempt: number;
  created_at?: string;
};

export type CandidateDataset = {
  id: string;
  job_id: string;
  name: string;
  kind: string;
  capabilities: string[];
  parent_ids: string[];
  state: "draft" | "sealed" | "partial" | "failed";
  row_count: number;
  metadata: Record<string, unknown>;
  created_at?: string;
};

export type CandidateRecord = {
  id: string;
  dataset_id: string;
  candidate_key: string;
  payload: Record<string, any>;
  tags: string[];
  included: boolean;
};

export type BrowserSession = {
  id: string;
  job_id: string;
  state: string;
  current_url?: string;
  locked_search_url?: string;
  viewer_url?: string;
  last_error?: string;
};

export const listStages = (jobId: string) => apiFetch<StageRun[]>(`/jobs/${jobId}/stage-runs`);
export const listDatasets = (jobId: string) => apiFetch<CandidateDataset[]>(`/jobs/${jobId}/datasets`);
export const createStage = (jobId: string, body: { stage_type: StageType; input_dataset_ids: string[]; config?: Record<string, unknown> }) =>
  apiFetch<StageRun>(`/jobs/${jobId}/stage-runs`, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ ...body, start: true }),
  });
export const controlStage = (stageId: string, action: "pause" | "resume" | "stop" | "skip" | "rerun" | "continue") =>
  apiFetch<StageRun>(`/stage-runs/${stageId}/${action}`, {
    method: "POST",
    headers: action === "rerun" ? { "Idempotency-Key": crypto.randomUUID() } : undefined,
  });
export const getRecords = (datasetId: string, search = "") =>
  apiFetch<{ records: CandidateRecord[]; total: number }>(`/datasets/${datasetId}/records?limit=200&search=${encodeURIComponent(search)}`);
export const patchRecord = (datasetId: string, recordId: string, body: Record<string, unknown>) =>
  apiFetch<{ dataset: CandidateDataset; record: CandidateRecord }>(`/datasets/${datasetId}/records/${recordId}`, {
    method: "PATCH", body: JSON.stringify(body),
  });
export const deleteRecord = (datasetId: string, recordId: string) =>
  apiFetch<CandidateDataset>(`/datasets/${datasetId}/records/${recordId}`, { method: "DELETE" });
export const sealDataset = (datasetId: string) => apiFetch<CandidateDataset>(`/datasets/${datasetId}/seal`, { method: "POST" });

export async function downloadDataset(dataset: CandidateDataset, format: "xlsx" | "csv" | "json") {
  const response = await fetch(`${API}/datasets/${dataset.id}/export?format=${format}`, { headers: getAuthHeaders() });
  if (!response.ok) throw new Error(await response.text());
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${dataset.name.replace(/\s+/g, "_")}.${format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function previewImport(file: File) {
  const body = new FormData(); body.append("file", file);
  const response = await fetch(`${API}/datasets/import/preview`, { method: "POST", headers: getAuthHeaders(), body });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function importDataset(jobId: string, file: File) {
  const body = new FormData(); body.append("file", file);
  const response = await fetch(`${API}/datasets/import?job_id=${jobId}&name=${encodeURIComponent(file.name)}`, {
    method: "POST", headers: getAuthHeaders(), body,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CandidateDataset>;
}

export const createBrowserSession = (jobId: string) => apiFetch<BrowserSession>("/browser-sessions", { method: "POST", body: JSON.stringify({ job_id: jobId }) });
export const getJobBrowserSession = (jobId: string) => apiFetch<BrowserSession | null>(`/jobs/${jobId}/browser-session`);
export const browserCommand = (sessionId: string, action: "open-search" | "lock-search" | "take-control" | "release-control", body: Record<string, unknown> = {}) =>
  apiFetch<BrowserSession>(`/browser-sessions/${sessionId}/${action}`, { method: "POST", body: JSON.stringify(body) });
