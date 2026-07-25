import type { CandidateDataset, StageRun, StageType } from "./workflow";

export const SOURCE_STAGE_TYPES: StageType[] = ["salesnav_extract", "telegram_extract", "apollo_extract", "file_import"];

export const SOURCE_PRESENTATION: Record<StageType, { label: string; icon: string; setup: string }> = {
  salesnav_extract: { label: "Sales Navigator", icon: "travel_explore", setup: "Set up a search" },
  telegram_extract: { label: "Telegram", icon: "send", setup: "Find channels" },
  apollo_extract: { label: "Apollo", icon: "person_search", setup: "Configure Apollo" },
  file_import: { label: "File import", icon: "upload_file", setup: "Upload a file" },
  merge_dedup: { label: "Merge & deduplicate", icon: "merge", setup: "Choose datasets" },
  profile_enrich: { label: "Enrich profiles", icon: "manage_search", setup: "Choose an input" },
  rules_filter: { label: "Rules filter", icon: "rule", setup: "Choose an input" },
  similarity_analyze: { label: "Similarity analysis", icon: "analytics", setup: "Choose an input" },
  ai_grade: { label: "AI grading", icon: "star", setup: "Choose an input" },
};

export function stageStatusLabel(run?: StageRun): string {
  if (!run) return "Not started";
  const source = SOURCE_STAGE_TYPES.includes(run.stage_type);
  const labels: Record<string, string> = {
    pending: "Waiting to start",
    running: source ? "Extracting candidates" : "Processing candidates",
    pause_requested: "Pausing safely",
    paused: "Paused",
    awaiting_auth: "Needs your LinkedIn approval",
    awaiting_user: "Dataset ready for review",
    completed: "Approved and complete",
    stopped: "Stopped — partial data kept",
    failed: "Needs attention",
    skipped: "Skipped",
  };
  return labels[run.status] || "In progress";
}

export function datasetStateLabel(dataset: CandidateDataset): string {
  return ({ draft: "Draft dataset", sealed: "Approved version", partial: "Partial dataset", failed: "Failed dataset" } as const)[dataset.state];
}
