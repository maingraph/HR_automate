"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, API } from "@/lib/api";
import { Card } from "@/components/ui";
import { useWebSocket } from "@/lib/hooks/useWebSocket";

// ── Types ─────────────────────────────────────────────────────────────────────

type PipelineRun = {
  id: string;
  stage: string;
  status: "started" | "ok" | "error";
  count: number;
  message?: string;
  started_at: string;
  ended_at?: string;
};

type JobStats = {
  linkedin_queries?: string[];
  geo_excluded?: number;
  [key: string]: number | string | string[] | undefined;
};

type Job = {
  id: string;
  title: string;
  status: string;
  linkedin_boolean?: string;
  tg_keywords?: string[];
  rubric?: Record<string, { weight: number; description: string }>;
  stats?: JobStats;
  geo_exclude?: string[];
  error?: string | null;
  checkpoint?: any;
};

type Candidate = {
  id: string;
  source: string;
  full_name?: string;
  username?: string;
  headline?: string;
  bio?: string;
  location?: string;
  skills?: string[];
  languages?: string[];
  linkedin_url?: string;
  telegram_url?: string;
  email?: string;
  phone?: string;
  gemini_score?: number;
  gemini_reasoning?: string;
  gemini_dimensions?: Record<string, number>;
  red_flags?: string[];
  open_to_work?: boolean;
  embed_similarity?: number;
  scan_depth?: number;
  status?: string;
  educations?: Array<{ school: string; field: string; location: string; start: string; end: string }>;
  positions?: Array<{ title: string; company: string; location: string; start: string; end: string; desc: string }>;
};

// ── Pipeline Stage Definitions ────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { id: "scrape", label: "Scrape", icon: "search" },
  { id: "normalize", label: "Normalize", icon: "filter_alt" },
  { id: "embed", label: "Embed", icon: "psychology" },
  { id: "deep", label: "Deep Scan", icon: "manage_search" },
  { id: "score", label: "Score", icon: "star" },
];

const STATUS_MAP: Record<string, { stage: string; label: string; color: string }> = {
  draft: { stage: "", label: "Draft", color: "text-[var(--muted)]" },
  queued: { stage: "scrape", label: "Queued", color: "text-yellow-400" },
  running: { stage: "scrape", label: "Running", color: "text-blue-400" },
  phase1_done: { stage: "embed", label: "Phase 1 Complete", color: "text-green-400" },
  running_deep: { stage: "deep", label: "Deep Scanning", color: "text-blue-400" },
  paused: { stage: "", label: "Paused", color: "text-yellow-400" },
  done: { stage: "score", label: "Complete", color: "text-green-400" },
  error: { stage: "", label: "Error", color: "text-red-400" },
};

// ── Main Component ────────────────────────────────────────────────────────────

export default function JobPage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<Job | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [logs, setLogs] = useState<PipelineRun[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  
  // Filter state
  const [minScore, setMinScore] = useState(0);
  const [srcFilter, setSrcFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    skills: [] as string[],
    location: "",
    minExperience: 0,
    maxExperience: 20,
    seniority: [] as string[],
    openToWork: null as boolean | null,
  });
  const [sortBy, setSortBy] = useState("score_desc");

  // Progress state
  const [progress, setProgress] = useState<Record<string, {
    current: number;
    total: number;
    percentage: number;
    message: string;
  }>>({});

  const loadJob = useCallback(async () => {
    const j = await apiFetch<Job>(`/jobs/${params.id}`).catch(() => null);
    setJob(j);
  }, [params.id]);

  const loadCandidates = useCallback(async () => {
    const q = new URLSearchParams({ limit: "2000" });
    if (minScore) q.set("min_score", String(minScore));
    if (srcFilter) q.set("source", srcFilter);
    if (filters.skills.length) q.set("skills", filters.skills.join(","));
    if (filters.location) q.set("location", filters.location);
    if (filters.minExperience > 0) q.set("min_experience", String(filters.minExperience));
    if (filters.maxExperience < 20) q.set("max_experience", String(filters.maxExperience));
    if (filters.seniority.length) q.set("seniority", filters.seniority.join(","));
    if (filters.openToWork !== null) q.set("open_to_work", String(filters.openToWork));
    q.set("sort_by", sortBy);
    
    const cs = await apiFetch<Candidate[]>(`/jobs/${params.id}/candidates?${q}`).catch(() => []);
    setCandidates(cs);
  }, [params.id, minScore, srcFilter, filters, sortBy]);

  const loadLogs = useCallback(async () => {
    const ls = await apiFetch<PipelineRun[]>(`/jobs/${params.id}/logs`).catch(() => []);
    setLogs(ls);
  }, [params.id]);

  const loadProgress = useCallback(async () => {
    const prog = await apiFetch<{progress: any}>(`/jobs/${params.id}/progress`).catch(() => ({ progress: {} }));
    setProgress(prog.progress || {});
  }, [params.id]);

  const load = useCallback(async () => {
    await Promise.all([loadJob(), loadCandidates(), loadLogs(), loadProgress()]);
  }, [loadJob, loadCandidates, loadLogs, loadProgress]);

  // WebSocket connection
  const { data: lastMessage } = useWebSocket(`/ws/jobs/${params.id}`);

  useEffect(() => {
    if (!lastMessage) return;
    const { type, data } = lastMessage;
    if (type === 'job_update') {
      setJob(prev => prev ? { ...prev, ...data } : null);
    } else if (type === 'pipeline_log') {
      setLogs(prev => {
        const existing = prev.find(l => l.id === data.id);
        if (existing) return prev.map(l => l.id === data.id ? data : l);
        return [...prev, data];
      });
    } else if (type === 'progress_update') {
      // Handle progress updates
      setProgress(prev => ({
        ...prev,
        [data.stage]: {
          current: data.current,
          total: data.total,
          percentage: data.percentage,
          message: data.message
        }
      }));
    } else if (type === 'candidates_update') {
      loadCandidates();
    }
  }, [lastMessage, loadCandidates]);

  useEffect(() => {
    load();
  }, [load]);

  // Computed values
  const statusInfo = STATUS_MAP[job?.status ?? "draft"] ?? STATUS_MAP.draft;
  const p1Candidates = useMemo(() => candidates.filter(c => (c.scan_depth ?? 1) === 1), [candidates]);
  const p2Candidates = useMemo(() => candidates.filter(c => (c.scan_depth ?? 1) === 2), [candidates]);
  const scoredCandidates = useMemo(
    () => candidates
      .filter(c => c.status !== "rejected")
      .sort((a, b) => {
        // Sort: scored candidates first (by score desc), then unscored
        const aScore = a.gemini_score ?? -1;
        const bScore = b.gemini_score ?? -1;
        if (aScore === -1 && bScore === -1) return 0;
        if (aScore === -1) return 1;
        if (bScore === -1) return -1;
        return bScore - aScore;
      }),
    [candidates]
  );

  // Filtered candidates for display
  const filteredCandidates = useMemo(() => {
    return scoredCandidates.filter(c => {
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          c.full_name?.toLowerCase().includes(q) ||
          c.headline?.toLowerCase().includes(q) ||
          c.skills?.some(s => s.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [scoredCandidates, searchQuery]);

  const isRunning = job?.status === "running" || job?.status === "running_deep" || job?.status === "queued";
  const isPaused = job?.status === "paused";
  const isDone = job?.status === "done";
  const hasError = job?.status === "error";

  // Actions
  const pauseJob = async () => {
    await apiFetch(`/jobs/${params.id}/pause`, { method: "POST" });
    await load();
  };

  const resumeJob = async () => {
    await apiFetch(`/jobs/${params.id}/resume`, { method: "POST" });
    await load();
  };

  const cancelJob = async () => {
    if (!confirm("Cancel this job? Partial results will be kept.")) return;
    await apiFetch(`/jobs/${params.id}/cancel`, { method: "POST" });
    await load();
  };

  const retryJob = async () => {
    await apiFetch(`/jobs/${params.id}/run`, { method: "POST" });
    await load();
  };

  const triggerDeepScan = async () => {
    await apiFetch(`/jobs/${params.id}/deep-scan`, { method: "POST" });
    await load();
  };

  const triggerScoreNow = async () => {
    await apiFetch(`/jobs/${params.id}/score-now`, { method: "POST" });
    await load();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <a href="/dashboard" className="text-[var(--muted)] hover:text-[var(--fg)] text-sm flex items-center gap-1">
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              Back to Dashboard
            </a>
          </div>
          <h1 className="text-3xl font-bold text-[var(--fg)] mb-2">{job?.title ?? "Loading..."}</h1>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${statusInfo.color} bg-[var(--panel)] border border-[var(--border)]`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5"></span>
              {statusInfo.label}
            </span>
            {job?.checkpoint && (
              <span className="text-xs text-[var(--muted)]">
                Checkpoint: {job.checkpoint.stage} ({job.checkpoint.scored_count || 0}/{job.checkpoint.total_count || 0})
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {isRunning && (
            <>
              <button onClick={pauseJob} className="px-4 py-2 text-sm rounded-lg border border-[var(--border)] text-[var(--fg2)] hover:bg-[var(--panel2)] transition-colors flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px]">pause</span>
                Pause
              </button>
              <button onClick={cancelJob} className="px-4 py-2 text-sm rounded-lg border border-red-600 text-red-400 hover:bg-red-900/20 transition-colors flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px]">close</span>
                Cancel
              </button>
            </>
          )}
          {isPaused && (
            <button onClick={resumeJob} className="px-4 py-2 text-sm rounded-lg border border-green-600 text-green-400 hover:bg-green-900/20 transition-colors flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">play_arrow</span>
              Resume
            </button>
          )}
          {hasError && (
            <button onClick={retryJob} className="px-4 py-2 text-sm rounded-lg border border-yellow-600 text-yellow-400 hover:bg-yellow-900/20 transition-colors flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">refresh</span>
              Retry
            </button>
          )}
          {isDone && (
            <a href={`${API}/jobs/${params.id}/export`} className="px-4 py-2 text-sm rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">download</span>
              Export
            </a>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {job?.error && (
        <div className="p-4 bg-red-900/30 border border-red-700 rounded-lg">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-red-400">error</span>
            <div className="flex-1">
              <div className="font-medium text-red-400 mb-1">Pipeline Error</div>
              <div className="text-sm text-red-200">{job.error}</div>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline Tracker */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-[var(--fg)] mb-4">Pipeline Progress</h2>
        <div className="flex items-center justify-between relative">
          {PIPELINE_STAGES.map((stage, idx) => {
            const isActive = statusInfo.stage === stage.id;
            const isComplete = PIPELINE_STAGES.findIndex(s => s.id === statusInfo.stage) > idx;
            const stageLog = logs.find(l => l.stage === stage.id);
            const stageProgress = progress[stage.id];
            
            return (
              <div key={stage.id} className="flex-1 relative">
                <div className="flex flex-col items-center">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all ${
                    isComplete ? "bg-[var(--green)] border-[var(--green)] text-white" :
                    isActive ? "bg-[var(--accent)] border-[var(--accent)] text-white animate-pulse" :
                    "bg-[var(--panel)] border-[var(--border)] text-[var(--muted)]"
                  }`}>
                    <span className="material-symbols-outlined text-[24px]">{stage.icon}</span>
                  </div>
                  <div className="mt-2 text-xs font-medium text-[var(--fg2)] text-center">{stage.label}</div>
                  
                  {/* Progress bar */}
                  {stageProgress && (
                    <div className="mt-2 w-full px-2">
                      <div className="w-full bg-[var(--panel2)] rounded-full h-1 overflow-hidden">
                        <div 
                          className={`h-full transition-all duration-300 ${
                            isComplete ? 'bg-[var(--green)]' : 'bg-[var(--accent)]'
                          }`}
                          style={{ width: `${Math.min(stageProgress.percentage, 100)}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-[var(--muted)] text-center mt-1">
                        {stageProgress.current}/{stageProgress.total}
                      </div>
                    </div>
                  )}
                  
                  {!stageProgress && stageLog && (
                    <div className="mt-1 text-[10px] text-[var(--muted)] text-center">
                      {stageLog.count > 0 && `${stageLog.count} items`}
                    </div>
                  )}
                </div>
                {idx < PIPELINE_STAGES.length - 1 && (
                  <div className={`absolute top-6 left-1/2 w-full h-0.5 -z-10 ${
                    isComplete ? "bg-[var(--green)]" : "bg-[var(--border)]"
                  }`} />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">Phase 1 Collected</div>
          <div className="text-2xl font-bold text-[var(--fg)]">{p1Candidates.length}</div>
          <div className="text-xs text-[var(--muted)] mt-1">Shallow profiles</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">Deep Scanned</div>
          <div className="text-2xl font-bold text-[var(--fg)]">{p2Candidates.length}</div>
          <div className="text-xs text-[var(--muted)] mt-1">Full profiles</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">Scored</div>
          <div className="text-2xl font-bold text-[var(--green)]">{scoredCandidates.length}</div>
          <div className="text-xs text-[var(--muted)] mt-1">Ranked candidates</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">Geo Excluded</div>
          <div className="text-2xl font-bold text-[var(--fg)]">{job?.stats?.geo_excluded ?? 0}</div>
          <div className="text-xs text-[var(--muted)] mt-1">Filtered out</div>
        </Card>
      </div>

      {/* Action Buttons */}
      {job?.status === "phase1_done" && (
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-[var(--fg)] mb-1">Phase 1 Complete</div>
              <div className="text-sm text-[var(--muted)]">Ready to deep scan {p1Candidates.filter(c => c.linkedin_url).length} LinkedIn profiles</div>
            </div>
            <button onClick={triggerDeepScan} className="px-4 py-2 text-sm rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors">
              Start Deep Scan
            </button>
          </div>
        </Card>
      )}

      {job?.status === "running_deep" && p2Candidates.length > 0 && scoredCandidates.length === 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-[var(--fg)] mb-1">Deep Scan In Progress</div>
              <div className="text-sm text-[var(--muted)]">{p2Candidates.length} profiles ready for scoring</div>
            </div>
            <button onClick={triggerScoreNow} className="px-4 py-2 text-sm rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors">
              Start Scoring
            </button>
          </div>
        </Card>
      )}

      {/* Candidates Section */}
      <Card className="overflow-hidden">
        <div className="p-4 border-b border-[var(--border)]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-[var(--fg)]">
              Top Candidates ({filteredCandidates.length})
            </h2>
          </div>
          
          <div className="flex items-center gap-2 flex-wrap">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px]">
              <span className="material-symbols-outlined absolute left-3 top-1/2 transform -translate-y-1/2 text-[var(--muted)] text-[18px]">search</span>
              <input
                type="text"
                placeholder="Search by name, skill..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)] placeholder-[var(--muted)] focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
              />
            </div>
            
            {/* Min Score */}
            <input
              type="number"
              placeholder="Min score"
              value={minScore || ""}
              onChange={(e) => setMinScore(+e.target.value)}
              className="px-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)] placeholder-[var(--muted)] w-24"
            />
            
            {/* Source Filter */}
            <select
              value={srcFilter}
              onChange={(e) => setSrcFilter(e.target.value)}
              className="px-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)]"
            >
              <option value="">All sources</option>
              <option value="linkedin">LinkedIn</option>
              <option value="telegram">Telegram</option>
              <option value="apollo">Apollo</option>
            </select>
            
            {/* Advanced Filters Button */}
            <div className="relative">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="px-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg2)] hover:bg-[var(--panel2)] transition-colors flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">filter_list</span>
                Filters
                {(filters.skills.length > 0 || filters.location || filters.seniority.length > 0 || filters.openToWork !== null) && (
                  <span className="ml-1 px-1.5 py-0.5 rounded-full bg-[var(--accent)] text-white text-xs">
                    {[filters.skills.length > 0, filters.location, filters.seniority.length > 0, filters.openToWork !== null].filter(Boolean).length}
                  </span>
                )}
              </button>
              
              {/* Filters Dropdown */}
              {showFilters && (
                <div className="absolute top-full right-0 mt-2 w-80 bg-[var(--surface)] border border-[var(--border)] rounded-lg shadow-2xl z-50 p-4 space-y-4">
                  {/* Location */}
                  <div>
                    <label className="text-xs font-medium text-[var(--fg2)] mb-1 block">Location</label>
                    <input
                      type="text"
                      placeholder="e.g., San Francisco"
                      value={filters.location}
                      onChange={(e) => setFilters({...filters, location: e.target.value})}
                      className="w-full px-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)] placeholder-[var(--muted)]"
                    />
                  </div>
                  
                  {/* Experience Range */}
                  <div>
                    <label className="text-xs font-medium text-[var(--fg2)] mb-1 block">
                      Experience: {filters.minExperience}-{filters.maxExperience} years
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={filters.minExperience}
                        onChange={(e) => setFilters({...filters, minExperience: +e.target.value})}
                        className="w-20 px-2 py-1 bg-[var(--panel)] border border-[var(--border)] rounded text-sm text-[var(--fg)]"
                      />
                      <span className="text-[var(--muted)]">to</span>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={filters.maxExperience}
                        onChange={(e) => setFilters({...filters, maxExperience: +e.target.value})}
                        className="w-20 px-2 py-1 bg-[var(--panel)] border border-[var(--border)] rounded text-sm text-[var(--fg)]"
                      />
                    </div>
                  </div>
                  
                  {/* Seniority */}
                  <div>
                    <label className="text-xs font-medium text-[var(--fg2)] mb-2 block">Seniority</label>
                    <div className="space-y-1">
                      {["Junior", "Mid", "Senior", "Lead", "Principal", "Staff"].map(level => (
                        <label key={level} className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={filters.seniority.includes(level)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setFilters({...filters, seniority: [...filters.seniority, level]});
                              } else {
                                setFilters({...filters, seniority: filters.seniority.filter(s => s !== level)});
                              }
                            }}
                            className="rounded border-[var(--border)]"
                          />
                          <span className="text-sm text-[var(--fg2)]">{level}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  
                  {/* Open to Work */}
                  <div>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={filters.openToWork === true}
                        onChange={(e) => setFilters({...filters, openToWork: e.target.checked ? true : null})}
                        className="rounded border-[var(--border)]"
                      />
                      <span className="text-sm text-[var(--fg2)]">Open to work only</span>
                    </label>
                  </div>
                  
                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-2 border-t border-[var(--border)]">
                    <button
                      onClick={() => setFilters({
                        skills: [],
                        location: "",
                        minExperience: 0,
                        maxExperience: 20,
                        seniority: [],
                        openToWork: null,
                      })}
                      className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] text-[var(--fg2)] hover:bg-[var(--panel2)] transition-colors"
                    >
                      Clear all
                    </button>
                    <button
                      onClick={() => setShowFilters(false)}
                      className="flex-1 px-3 py-1.5 text-sm rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors"
                    >
                      Apply
                    </button>
                  </div>
                </div>
              )}
            </div>
            
            {/* Sort Dropdown */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)]"
            >
              <option value="score_desc">Score: High to Low</option>
              <option value="score_asc">Score: Low to High</option>
              <option value="name_asc">Name: A-Z</option>
              <option value="name_desc">Name: Z-A</option>
              <option value="date_desc">Date: Newest</option>
              <option value="date_asc">Date: Oldest</option>
              <option value="location_asc">Location: A-Z</option>
            </select>
            
            {/* Sort Dropdown */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)]"
            >
              <option value="score_desc">Score: High to Low</option>
              <option value="score_asc">Score: Low to High</option>
              <option value="name_asc">Name: A-Z</option>
              <option value="name_desc">Name: Z-A</option>
              <option value="date_desc">Date: Newest</option>
              <option value="date_asc">Date: Oldest</option>
              <option value="location_asc">Location: A-Z</option>
            </select>
            
            {/* Filters Button */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="px-3 py-1.5 bg-[var(--panel)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)] hover:bg-[var(--panel2)] transition-colors flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[18px]">tune</span>
              Filters
              {(filters.skills.length > 0 || filters.location || filters.seniority.length > 0 || filters.openToWork !== null) && (
                <span className="px-1.5 py-0.5 rounded-full bg-[var(--accent)] text-white text-xs">
                  {filters.skills.length + (filters.location ? 1 : 0) + filters.seniority.length + (filters.openToWork !== null ? 1 : 0)}
                </span>
              )}
            </button>
          </div>
          
          {/* Advanced Filters Panel */}
          {showFilters && (
            <div className="mt-3 p-4 bg-[var(--panel)] border border-[var(--border)] rounded-lg space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {/* Location */}
                <div>
                  <label className="text-xs font-medium text-[var(--fg2)] mb-1 block">Location</label>
                  <input
                    type="text"
                    placeholder="e.g., San Francisco"
                    value={filters.location}
                    onChange={(e) => setFilters({...filters, location: e.target.value})}
                    className="w-full px-3 py-1.5 bg-[var(--surface)] border border-[var(--border)] rounded-lg text-sm text-[var(--fg)] placeholder-[var(--muted)]"
                  />
                </div>
                
                {/* Seniority */}
                <div>
                  <label className="text-xs font-medium text-[var(--fg2)] mb-1 block">Seniority</label>
                  <div className="flex flex-wrap gap-2">
                    {["Junior", "Mid", "Senior", "Lead"].map(level => (
                      <label key={level} className="flex items-center gap-1 text-sm">
                        <input
                          type="checkbox"
                          checked={filters.seniority.includes(level)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFilters({...filters, seniority: [...filters.seniority, level]});
                            } else {
                              setFilters({...filters, seniority: filters.seniority.filter(s => s !== level)});
                            }
                          }}
                          className="rounded"
                        />
                        <span className="text-[var(--fg2)]">{level}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              
              {/* Experience Range */}
              <div>
                <label className="text-xs font-medium text-[var(--fg2)] mb-1 block">
                  Experience: {filters.minExperience}-{filters.maxExperience} years
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="20"
                    value={filters.minExperience}
                    onChange={(e) => setFilters({...filters, minExperience: +e.target.value})}
                    className="flex-1"
                  />
                  <span className="text-xs text-[var(--muted)] w-8">to</span>
                  <input
                    type="range"
                    min="0"
                    max="20"
                    value={filters.maxExperience}
                    onChange={(e) => setFilters({...filters, maxExperience: +e.target.value})}
                    className="flex-1"
                  />
                </div>
              </div>
              
              {/* Open to Work */}
              <div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={filters.openToWork === true}
                    onChange={(e) => setFilters({...filters, openToWork: e.target.checked ? true : null})}
                    className="rounded"
                  />
                  <span className="text-[var(--fg2)]">Open to work only</span>
                </label>
              </div>
              
              {/* Clear Filters */}
              <div className="flex justify-end">
                <button
                  onClick={() => setFilters({
                    skills: [],
                    location: "",
                    minExperience: 0,
                    maxExperience: 20,
                    seniority: [],
                    openToWork: null,
                  })}
                  className="px-3 py-1.5 text-sm text-[var(--muted)] hover:text-[var(--fg)] transition-colors"
                >
                  Clear all filters
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="divide-y divide-[var(--border)]">
          {filteredCandidates.length === 0 ? (
            <div className="p-12 text-center">
              <span className="material-symbols-outlined text-[48px] text-[var(--muted)] mb-2">person_search</span>
              <div className="text-[var(--muted)]">No candidates yet</div>
            </div>
          ) : (
            filteredCandidates.map((candidate) => (
              <CandidateCard
                key={candidate.id}
                candidate={candidate}
                expanded={expandedId === candidate.id}
                onToggle={() => setExpandedId(expandedId === candidate.id ? null : candidate.id)}
              />
            ))
          )}
        </div>
      </Card>

      {/* Logs Section */}
      <Card className="overflow-hidden">
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[var(--accent)]">smart_toy</span>
            <h2 className="text-lg font-semibold text-[var(--fg)]">Pipeline Logs</h2>
          </div>
          {isRunning && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--green)] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[var(--green)]"></span>
            </span>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--panel)] border-b border-[var(--border)]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wider">Stage</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wider">Count</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wider">Message</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted)] uppercase tracking-wider">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted)]">No logs yet</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-[var(--panel)] transition-colors">
                    <td className="px-4 py-3 text-[var(--fg2)]">{log.stage}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        log.status === "ok" ? "bg-green-900/30 text-green-400" :
                        log.status === "error" ? "bg-red-900/30 text-red-400" :
                        "bg-yellow-900/30 text-yellow-400"
                      }`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--fg2)]">{log.count}</td>
                    <td className="px-4 py-3 text-[var(--muted)] max-w-md truncate">{log.message || "—"}</td>
                    <td className="px-4 py-3 text-[var(--muted)] text-xs">{new Date(log.started_at).toLocaleString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ── Candidate Card Component ──────────────────────────────────────────────────

function CandidateCard({ candidate, expanded, onToggle }: {
  candidate: Candidate;
  expanded: boolean;
  onToggle: () => void;
}) {
  const score = candidate.gemini_score ?? null;
  const scoreColor = score === null ? "text-[var(--muted)]" : score >= 80 ? "text-green-400" : score >= 60 ? "text-blue-400" : "text-yellow-400";
  const scoreDisplay = score === null ? "?" : score;

  return (
    <div className="p-4 hover:bg-[var(--panel)] transition-colors">
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-full border-2 flex items-center justify-center font-bold ${scoreColor}`}>
          {scoreDisplay}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-[var(--fg)] truncate">{candidate.full_name || candidate.username || "Unknown"}</h3>
              <p className="text-sm text-[var(--muted)] truncate">{candidate.headline || "No headline"}</p>
              <div className="flex items-center gap-3 mt-2 text-xs text-[var(--muted)]">
                {candidate.location && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">location_on</span>
                    {candidate.location}
                  </span>
                )}
                {candidate.source && (
                  <span className="px-2 py-0.5 rounded bg-[var(--panel2)] text-[var(--fg2)]">{candidate.source}</span>
                )}
                {candidate.open_to_work && (
                  <span className="px-2 py-0.5 rounded bg-green-900/30 text-green-400">Open to work</span>
                )}
              </div>
            </div>
            <button onClick={onToggle} className="text-[var(--accent)] hover:text-[var(--accent-hover)] text-sm font-medium">
              {expanded ? "Hide" : "View"} Details
            </button>
          </div>

          {expanded && (
            <div className="mt-4 pt-4 border-t border-[var(--border)] space-y-4">
              {candidate.gemini_reasoning && (
                <div>
                  <div className="text-xs font-medium text-[var(--muted)] uppercase mb-1">AI Reasoning</div>
                  <div className="text-sm text-[var(--fg2)]">{candidate.gemini_reasoning}</div>
                </div>
              )}
              {candidate.skills && candidate.skills.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-[var(--muted)] uppercase mb-2">Skills</div>
                  <div className="flex flex-wrap gap-2">
                    {candidate.skills.map((skill, idx) => (
                      <span key={idx} className="px-2 py-1 rounded bg-[var(--panel2)] text-xs text-[var(--fg2)]">{skill}</span>
                    ))}
                  </div>
                </div>
              )}
              {candidate.positions && candidate.positions.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-[var(--muted)] uppercase mb-2">Experience</div>
                  <div className="space-y-2">
                    {candidate.positions.slice(0, 3).map((pos, idx) => (
                      <div key={idx} className="text-sm">
                        <div className="font-medium text-[var(--fg)]">{pos.title} @ {pos.company}</div>
                        <div className="text-xs text-[var(--muted)]">{pos.start} - {pos.end}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex items-center gap-2">
                {candidate.linkedin_url && (
                  <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 text-xs rounded-lg border border-[var(--border)] text-[var(--fg2)] hover:bg-[var(--panel2)] transition-colors">
                    LinkedIn
                  </a>
                )}
                {candidate.email && (
                  <a href={`mailto:${candidate.email}`} className="px-3 py-1.5 text-xs rounded-lg border border-[var(--border)] text-[var(--fg2)] hover:bg-[var(--panel2)] transition-colors">
                    Email
                  </a>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
