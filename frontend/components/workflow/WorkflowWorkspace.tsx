"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWebSocket } from "@/lib/hooks/useWebSocket";
import {
  BrowserSession, CandidateDataset, CandidateRecord, StageRun, StageType,
  applyBrowserFilters, browserCommand, browserInput, controlStage, createBrowserSession, createStage, deleteRecord, downloadDataset,
  getBrowserFilterPlan, getJobBrowserSession, getRecords, importDataset, listDatasets, listStages, patchRecord, previewImport, searchTelegramChannels, TelegramChannelResult,
} from "@/lib/workflow";
import { datasetStateLabel, stageStatusLabel } from "@/lib/pipeline-presentation";

const CATALOG: Array<{ type: StageType; label: string; icon: string; phase: number; description: string; source?: boolean; requires?: string }> = [
  { type: "salesnav_extract", label: "Sales Navigator", icon: "travel_explore", phase: 1, description: "Collect profiles from locked SalesNav search.", source: true },
  { type: "telegram_extract", label: "Telegram", icon: "send", phase: 1, description: "Collect candidates from configured channels.", source: true },
  { type: "apollo_extract", label: "Apollo", icon: "person_search", phase: 1, description: "Collect candidates from Apollo.", source: true },
  { type: "file_import", label: "File Import", icon: "upload_file", phase: 1, description: "Start pipeline from CSV, XLSX, or JSON.", source: true },
  { type: "merge_dedup", label: "Merge & Dedup", icon: "merge", phase: 2, description: "Combine selected source datasets and remove duplicates.", requires: "Select source datasets" },
  { type: "profile_enrich", label: "Enrich Profiles", icon: "manage_search", phase: 3, description: "Add deeper profile and experience data.", requires: "Select normalized dataset" },
  { type: "rules_filter", label: "Rules Filter", icon: "rule", phase: 4, description: "Apply mandatory job rules without AI grading.", requires: "Select normalized dataset" },
  { type: "similarity_analyze", label: "Similarity", icon: "analytics", phase: 5, description: "Rank similarity; keep every candidate until review.", requires: "Select normalized dataset" },
  { type: "ai_grade", label: "AI Grade", icon: "star", phase: 6, description: "Optional final AI grading stage.", requires: "Select normalized dataset" },
];

const STATUS_COLORS: Record<string, string> = {
  running: "text-blue-400 border-blue-500/40", pause_requested: "text-yellow-400 border-yellow-500/40",
  paused: "text-yellow-400 border-yellow-500/40", awaiting_user: "text-purple-400 border-purple-500/40",
  awaiting_auth: "text-orange-400 border-orange-500/40", completed: "text-green-400 border-green-500/40",
  failed: "text-red-400 border-red-500/40", stopped: "text-[var(--muted)] border-[var(--border)]",
};

function StageCard({ definition, run, selectedInputs, onRun, onControl, onSelectOutput }: {
  definition: typeof CATALOG[number]; run?: StageRun; selectedInputs: string[];
  onRun: () => void; onControl: (action: "pause" | "resume" | "stop" | "skip" | "rerun" | "continue") => void;
  onSelectOutput: () => void;
}) {
  const active = run && ["pending", "running", "pause_requested", "paused", "awaiting_auth"].includes(run.status);
  const rerunnable = definition.type !== "telegram_extract" || Array.isArray(run?.config?.channels) && run!.config.channels.length > 0;
  const pct = run?.progress?.percentage || 0;
  return (
    <div className={`rounded-xl border bg-[var(--panel)] p-4 ${run ? STATUS_COLORS[run.status] || "border-[var(--border)]" : "border-[var(--border)]"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex gap-3">
          <span className="material-symbols-outlined text-[22px] text-[var(--accent)]">{definition.icon}</span>
          <div>
            <div className="font-medium text-[var(--fg)]">Phase {definition.phase} · {definition.label}</div>
            <div className="text-xs text-[var(--muted)] mt-0.5">{run ? `${stageStatusLabel(run)} · run ${run.attempt}` : definition.requires || "Independent source tool"}</div>
            <div className="text-[11px] text-[var(--muted)] mt-1">{definition.description}</div>
          </div>
        </div>
        {run?.output_dataset_id && <button onClick={onSelectOutput} className="text-xs text-[var(--accent)] hover:underline">Open data</button>}
      </div>
      {run && (run.status === "running" || run.status === "pause_requested") && (
        <div className="mt-3"><div className="h-1.5 rounded bg-[var(--panel2)] overflow-hidden"><div className="h-full bg-[var(--accent)]" style={{ width: `${pct}%` }} /></div><div className="text-[10px] text-[var(--muted)] mt-1">{run.progress.current || 0}/{run.progress.total || "?"}</div></div>
      )}
      {run?.error && <div className="mt-2 text-xs text-red-400 line-clamp-2">{run.error}</div>}
      <div className="flex flex-wrap gap-2 mt-4">
        {!active && run?.status !== "awaiting_user" && <button onClick={onRun} disabled={!definition.source && selectedInputs.length === 0} className="btn-primary text-xs px-3 py-1.5 disabled:opacity-40">{run ? definition.type === "telegram_extract" ? "New configured run" : "New run" : "Start"}</button>}
        {run?.status === "running" && <button onClick={() => onControl("pause")} className="btn-secondary text-xs px-3 py-1.5">Pause</button>}
        {run?.status === "paused" && <button onClick={() => onControl("resume")} className="btn-primary text-xs px-3 py-1.5">Resume</button>}
        {run?.status === "awaiting_auth" && <button onClick={() => onControl("resume")} className="btn-primary text-xs px-3 py-1.5">Auth complete</button>}
        {active && <button onClick={() => onControl("stop")} className="text-xs px-3 py-1.5 rounded border border-red-500/50 text-red-400">Stop now</button>}
        {run?.status === "awaiting_user" && <button onClick={() => onControl("continue")} className="btn-primary text-xs px-3 py-1.5">Approve dataset & continue</button>}
        {run && rerunnable && ["completed", "failed", "stopped", "skipped"].includes(run.status) && <button onClick={() => onControl("rerun")} className="btn-secondary text-xs px-3 py-1.5">Rerun same setup</button>}
        {!run && !definition.source && <span className="text-[10px] text-[var(--muted)] self-center">{selectedInputs.length} input(s)</span>}
      </div>
    </div>
  );
}

function DatasetGate({ dataset, onChanged }: { dataset: CandidateDataset; onChanged: (dataset?: CandidateDataset) => void }) {
  const [records, setRecords] = useState<CandidateRecord[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRecords((await getRecords(dataset.id, search)).records); } finally { setLoading(false); }
  }, [dataset.id, search]);
  useEffect(() => { load(); }, [load]);

  const update = async (record: CandidateRecord, changes: Record<string, unknown>) => {
    const result = await patchRecord(dataset.id, record.id, changes);
    if (result.dataset.id !== dataset.id) onChanged(result.dataset);
    else await load();
  };
  const edit = async (record: CandidateRecord, key: string) => {
    const next = prompt(`Edit ${key}`, String(record.payload[key] || ""));
    if (next === null) return;
    await update(record, { payload: { ...record.payload, [key]: next } });
  };
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--panel)] overflow-hidden">
      <div className="p-4 border-b border-[var(--border)] flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-52"><div className="font-medium text-[var(--fg)]">{dataset.name}</div><div className="text-xs text-[var(--muted)]">{dataset.kind} · {datasetStateLabel(dataset)} · {dataset.row_count} rows · v{dataset.id.slice(0, 8)}</div></div>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search dataset" className="input text-sm w-52" />
        {(["xlsx", "csv", "json"] as const).map(format => <button key={format} onClick={() => downloadDataset(dataset, format)} className="btn-secondary text-xs px-3 py-1.5">{format.toUpperCase()}</button>)}
      </div>
      <div className="overflow-x-auto max-h-[430px]">
        <table className="w-full text-sm"><thead className="sticky top-0 bg-[var(--surface)]"><tr className="text-left text-xs text-[var(--muted)]"><th className="p-3">Use</th><th className="p-3">Name</th><th className="p-3">Headline</th><th className="p-3">Location</th><th className="p-3">Source</th><th className="p-3">Score</th><th className="p-3">Tags</th><th className="p-3"></th></tr></thead>
          <tbody>{records.map(record => <tr key={record.id} className="border-t border-[var(--border)] hover:bg-[var(--panel2)]">
            <td className="p-3"><input type="checkbox" checked={record.included} onChange={e => update(record, { included: e.target.checked })} /></td>
            <td className="p-3 cursor-pointer" onDoubleClick={() => edit(record, "full_name")}>{record.payload.full_name || record.payload.username || "—"}</td>
            <td className="p-3 max-w-72 truncate cursor-pointer" onDoubleClick={() => edit(record, "headline")}>{record.payload.headline || "—"}</td>
            <td className="p-3 cursor-pointer" onDoubleClick={() => edit(record, "location")}>{record.payload.location || "—"}</td>
            <td className="p-3">{record.payload.source || "—"}</td><td className="p-3">{record.payload.gemini_score ?? "—"}</td>
            <td className="p-3 cursor-pointer" onClick={async () => { const tags = prompt("Comma-separated tags", (record.tags || []).join(", ")); if (tags !== null) await update(record, { tags: tags.split(",").map(v => v.trim()).filter(Boolean) }); }}>{(record.tags || []).join(", ") || "+ tag"}</td>
            <td className="p-3">{dataset.state !== "sealed" && <button className="text-red-400 text-xs" onClick={async () => { if (confirm("Delete this candidate from draft dataset?")) { await deleteRecord(dataset.id, record.id); await load(); onChanged(); } }}>Delete</button>}</td>
          </tr>)}</tbody></table>
        {!loading && records.length === 0 && <div className="p-8 text-center text-[var(--muted)]">No records</div>}
        {loading && <div className="p-8 text-center text-[var(--muted)]">Loading…</div>}
      </div>
      <div className="px-4 py-2 text-[10px] text-[var(--muted)] border-t border-[var(--border)]">Double-click name, headline, or location to edit. Editing an approved version creates an editable copy.</div>
    </div>
  );
}

function BrowserPanel({ jobId, session, onSession, openRequested, onOpenHandled }: { jobId: string; session: BrowserSession | null; onSession: (s: BrowserSession) => void; openRequested: boolean; onOpenHandled: () => void }) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [inputText, setInputText] = useState("");
  const [privateInput, setPrivateInput] = useState(true);
  const [inputError, setInputError] = useState("");
  useEffect(() => { if (openRequested) { setOpen(true); onOpenHandled(); } }, [openRequested, onOpenHandled]);
  const command = async (action: "open-search" | "lock-search" | "take-control" | "release-control") => {
    if (!session) return;
    setBusy(true); try { onSession(await browserCommand(session.id, action)); } finally { setBusy(false); }
  };
  const start = async () => { setBusy(true); try { onSession(await createBrowserSession(jobId)); } finally { setBusy(false); } };
  const prepareFilters = async () => {
    if (!session) return;
    setBusy(true);
    try {
      const plan = await getBrowserFilterPlan(session.id);
      const approved = confirm([
        "Apply these Sales Navigator filters?",
        "",
        `Keywords: ${plan.keywords}`,
        `Current title: ${plan.current_title}`,
        `Function: ${plan.function}`,
        `Geography: ${plan.geography}`,
        `Seniority: ${plan.seniority || "kept in keywords"}`,
        "",
        ...plan.notes,
      ].join("\n"));
      if (!approved) return;
      onSession(await applyBrowserFilters(session.id));
    } catch (error) {
      setInputError(error instanceof Error ? error.message : "Filter application failed");
    } finally {
      setBusy(false);
    }
  };
  const sendInput = async (body: { text?: string; key?: "Backspace" | "Delete" | "Tab" | "Enter" | "Escape" | "Control+A" }) => {
    if (!session) return;
    setInputError("");
    setBusy(true);
    try {
      await browserInput(session.id, body);
      if (body.text) setInputText("");
    } catch (error) {
      setInputError(error instanceof Error ? error.message : "Browser input failed");
    } finally {
      setBusy(false);
    }
  };
  const visible = open || session?.state === "awaiting_auth";
  return <div id="browser-workspace" className={`${expanded ? "relative z-10 -mx-3 md:-mx-6 shadow-xl" : ""} rounded-xl border border-[var(--border)] bg-[var(--panel)] overflow-hidden`}>
    <div className="p-4 flex flex-wrap items-center gap-2 border-b border-[var(--border)]"><div className="flex-1"><div className="font-medium text-[var(--fg)]">Interactive Sales Navigator</div><div className="text-xs text-[var(--muted)]">{session?.state || "Browser stopped"}{session?.current_url ? ` · ${session.current_url}` : ""}</div></div>
      {!session && <button disabled={busy} onClick={start} className="btn-primary text-xs px-3 py-1.5">Start browser</button>}
      {session && <button onClick={() => setOpen(value => !value)} className="btn-secondary text-xs px-3 py-1.5">{visible ? "Hide browser" : "Open Sales Navigator"}</button>}
      {session && visible && <><button disabled={busy} onClick={() => command("open-search")} className="btn-secondary text-xs px-3 py-1.5">Open AI search</button><button disabled={busy} onClick={prepareFilters} className="btn-secondary text-xs px-3 py-1.5">Apply job filters</button><button disabled={busy} onClick={() => command("lock-search")} className="btn-primary text-xs px-3 py-1.5">Lock search</button><button disabled={busy} onClick={() => command("take-control")} className="btn-secondary text-xs px-3 py-1.5">Take control</button><button disabled={busy} onClick={() => command("release-control")} className="btn-secondary text-xs px-3 py-1.5">Release</button><button onClick={() => setExpanded(value => !value)} className="btn-secondary text-xs px-3 py-1.5">{expanded ? "Normal size" : "Larger browser"}</button></>}
    </div>
    {visible && session?.state === "awaiting_auth" && <div className="p-3 bg-orange-500/10 text-orange-300 border-b border-orange-500/30">LinkedIn needs login or mobile approval. Complete it in browser, then lock search.</div>}
    {visible && session && <div className="p-3 border-b border-[var(--border)] bg-[var(--surface)]">
      <div className="text-xs text-[var(--muted)] mb-2">Click a field inside Sales Navigator, then type or paste here. Text is sent directly to Chromium and never stored.</div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type={privateInput ? "password" : "text"}
          value={inputText}
          onChange={event => setInputText(event.target.value)}
          placeholder="Text for focused browser field"
          autoComplete="off"
          className="input text-sm flex-1 min-w-60"
        />
        <label className="text-xs text-[var(--muted)] flex items-center gap-1">
          <input type="checkbox" checked={privateInput} onChange={event => setPrivateInput(event.target.checked)} />
          Hide text
        </label>
        <button disabled={busy || !inputText} onClick={() => sendInput({ text: inputText })} className="btn-primary text-xs px-3 py-1.5 disabled:opacity-40">Send text</button>
        <button disabled={busy} onClick={() => sendInput({ key: "Control+A" })} className="btn-secondary text-xs px-3 py-1.5">Select all</button>
        {(["Backspace", "Delete", "Tab", "Enter"] as const).map(key => (
          <button key={key} disabled={busy} onClick={() => sendInput({ key })} className="btn-secondary text-xs px-3 py-1.5">{key}</button>
        ))}
      </div>
      {inputError && <div className="text-xs text-red-400 mt-2">{inputError}</div>}
    </div>}
    {visible && (session?.viewer_url ? <iframe title="Sales Navigator browser" src={session.viewer_url} className={`w-full bg-black ${expanded ? "h-[800px]" : "h-[700px]"}`} allow="clipboard-read; clipboard-write" /> : <div className="h-48 grid place-items-center text-[var(--muted)]">Start browser to open embedded noVNC viewer.</div>)}
  </div>;
}

export type WorkflowWorkspaceMode = "sources" | "pipeline" | "datasets";

export function WorkflowWorkspace({ jobId, mode = "sources" }: { jobId: string; mode?: WorkflowWorkspaceMode }) {
  const [stages, setStages] = useState<StageRun[]>([]);
  const [datasets, setDatasets] = useState<CandidateDataset[]>([]);
  const [selectedInputs, setSelectedInputs] = useState<string[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<CandidateDataset | null>(null);
  const [browser, setBrowser] = useState<BrowserSession | null>(null);
  const [salesnavLimit, setSalesnavLimit] = useState(3);
  const [telegramChannels, setTelegramChannels] = useState("");
  const [telegramKeywords, setTelegramKeywords] = useState("");
  const [telegramDays, setTelegramDays] = useState(30);
  const [telegramLimit, setTelegramLimit] = useState(100);
  const [showTelegramTools, setShowTelegramTools] = useState(false);
  const [browserRequested, setBrowserRequested] = useState(false);
  const [showBrowserWorkspace, setShowBrowserWorkspace] = useState(false);
  const [telegramQuery, setTelegramQuery] = useState("");
  const [telegramMatches, setTelegramMatches] = useState<TelegramChannelResult[]>([]);
  const [telegramSearching, setTelegramSearching] = useState(false);
  const [activePipelineId, setActivePipelineId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: event } = useWebSocket<any>(`/ws/jobs/${jobId}`);
  const load = useCallback(async () => {
    const [nextStages, nextDatasets, nextBrowser] = await Promise.all([listStages(jobId), listDatasets(jobId), getJobBrowserSession(jobId)]);
    setStages(nextStages); setDatasets(nextDatasets);
    if (nextBrowser) setBrowser(nextBrowser);
    if (selectedDataset) setSelectedDataset(nextDatasets.find(d => d.id === selectedDataset.id) || selectedDataset);
    else if (nextDatasets.length) setSelectedDataset(nextDatasets.find(d => d.kind === "graded") || nextDatasets[0]);
  }, [jobId, selectedDataset]);
  useEffect(() => { load().catch(e => setError(e.message)); }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!event) return; load(); if (event.type === "browser.auth_required") { try { const context = new AudioContext(); const oscillator = context.createOscillator(); oscillator.connect(context.destination); oscillator.start(); oscillator.stop(context.currentTime + 0.2); new Notification("Sourcer needs LinkedIn approval", { body: "Complete login in embedded browser." }); } catch {} } }, [event]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (typeof Notification !== "undefined" && Notification.permission === "default") Notification.requestPermission(); }, []);

  const pipelineKeyByStage = useMemo(() => {
    const producer = new Map(stages.filter(stage => stage.output_dataset_id).map(stage => [stage.output_dataset_id!, stage]));
    const keys = new Map<string, string>();
    for (const stage of stages) {
      const inputKeys = [...new Set(stage.input_dataset_ids.map(id => producer.get(id)).filter(Boolean).map(parent => keys.get(parent!.id)).filter(Boolean))] as string[];
      if (CATALOG.find(item => item.type === stage.stage_type)?.source) keys.set(stage.id, `root:${stage.id}`);
      else if (inputKeys.length === 1) keys.set(stage.id, inputKeys[0]);
      else if (inputKeys.length > 1) keys.set(stage.id, `merge:${stage.id}`);
      else keys.set(stage.id, `orphan:${stage.id}`);
    }
    return keys;
  }, [stages]);
  const pipelines = useMemo(() => {
    const grouped = new Map<string, StageRun[]>();
    stages.forEach(stage => { const key = pipelineKeyByStage.get(stage.id)!; grouped.set(key, [...(grouped.get(key) || []), stage]); });
    return [...grouped.entries()].map(([id, runs]) => {
      const root = runs[0];
      const source = CATALOG.find(item => item.type === root.stage_type)?.label || root.stage_type;
      return { id, runs, root, label: id.startsWith("merge:") ? `Combined pipeline · ${source}` : `${source} pipeline`, createdAt: root.created_at };
    }).sort((left, right) => Date.parse(right.createdAt || "0") - Date.parse(left.createdAt || "0"));
  }, [stages, pipelineKeyByStage]);
  const activePipeline = pipelines.find(pipeline => pipeline.id === activePipelineId) || pipelines[0];
  const activeStages = activePipeline?.runs || [];
  const latest = useMemo(() => Object.fromEntries(CATALOG.map(item => [item.type, activeStages.filter(s => s.stage_type === item.type).at(-1)])), [activeStages]);
  useEffect(() => { if (activePipeline && activePipelineId !== activePipeline.id) setActivePipelineId(activePipeline.id); }, [activePipeline, activePipelineId]);
  useEffect(() => {
    const outputId = activePipeline?.runs.at(-1)?.output_dataset_id;
    const output = datasets.find(dataset => dataset.id === outputId);
    if (output) setSelectedDataset(output);
  }, [activePipeline?.id, datasets]);
  const run = async (type: StageType) => {
    if (type === "file_import") { fileRef.current?.click(); return; }
    const config: Record<string, unknown> = {};
    if (type === "salesnav_extract") {
      if (!browser?.id || !browser.locked_search_url) throw new Error("Start browser and lock Sales Navigator search first");
      config.browser_session_id = browser.id;
      config.max_profiles = Math.max(1, Math.min(200, salesnavLimit));
      config.max_pages = Math.max(1, Math.ceil(Number(config.max_profiles) / 25));
    }
    if (type === "profile_enrich") {
      config.provider = browser?.id ? "local" : "existing";
      if (browser?.id) config.browser_session_id = browser.id;
    }
    if (type === "telegram_extract") {
      const channels = telegramChannels.split(/[\s,]+/).map(value => value.trim()).filter(Boolean);
      if (!channels.length) throw new Error("Add at least one Telegram channel (for example @pythonjobs) before starting Telegram extraction");
      config.channels = channels;
      config.keywords = telegramKeywords.split(",").map(value => value.trim()).filter(Boolean);
      config.days_back = Math.max(1, Math.min(365, telegramDays));
      config.per_channel_limit = Math.max(10, Math.min(1000, telegramLimit));
    }
    const stage = await createStage(jobId, { stage_type: type, input_dataset_ids: CATALOG.find(v => v.type === type)?.source ? [] : selectedInputs, config });
    if (CATALOG.find(v => v.type === type)?.source) setActivePipelineId(`root:${stage.id}`);
    await load();
  };
  const control = async (run: StageRun, action: "pause" | "resume" | "stop" | "skip" | "rerun" | "continue") => { await controlStage(run.id, action); await load(); };
  const upload = async (file: File) => {
    const preview = await previewImport(file);
    if (!confirm(`Import ${preview.row_count} rows with ${preview.columns.length} detected columns?`)) return;
    const dataset = await importDataset(jobId, file); await load(); setSelectedDataset(dataset);
  };
  const findTelegramChannels = async () => {
    setTelegramSearching(true); setError(null);
    try { setTelegramMatches(await searchTelegramChannels(telegramQuery)); }
    catch (searchError) { setError(searchError instanceof Error ? searchError.message : "Telegram channel search failed"); }
    finally { setTelegramSearching(false); }
  };
  const addTelegramChannel = (handle: string) => {
    const current = telegramChannels.split(/[\s,]+/).map(value => value.trim()).filter(Boolean);
    if (!current.includes(handle)) setTelegramChannels([...current, handle].join(", "));
  };
  const removeTelegramChannel = (handle: string) => setTelegramChannels(current => current.split(/[\s,]+/).map(value => value.trim()).filter(value => value && value !== handle).join(", "));
  const selectedTelegramChannels = telegramChannels.split(/[\s,]+/).map(value => value.trim()).filter(Boolean);
  const rootRun = activePipeline?.root;
  const rootType = rootRun?.stage_type;
  const sourceRun = rootRun;
  const runForDataset = useMemo(() => new Map(stages.filter(stage => stage.output_dataset_id).map(stage => [stage.output_dataset_id!, stage])), [stages]);
  const formatTime = (value?: string) => value ? new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "Unknown time";
  const duration = (stage?: StageRun) => {
    if (!stage?.started_at || !stage.ended_at) return "";
    const seconds = Math.max(0, Math.round((Date.parse(stage.ended_at) - Date.parse(stage.started_at)) / 1000));
    return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  };
  const useOnlySource = () => {
    const output = sourceRun?.output_dataset_id;
    if (!output) return;
    setSelectedInputs([output]);
  };
  const skipEnrichment = async () => {
    if (!selectedInputs.length) throw new Error("Choose the dataset you want to carry forward first");
    await createStage(jobId, { stage_type: "profile_enrich", input_dataset_ids: selectedInputs, config: { provider: "skip" } });
    await load();
  };
  const completedAfter = (run?: StageRun, upstream?: StageRun) =>
    run?.status === "completed"
    && (!upstream?.created_at || !run.created_at || Date.parse(run.created_at) >= Date.parse(upstream.created_at));
  const extractDone = sourceRun?.status === "completed";
  const mergeDone = extractDone && completedAfter(latest.merge_dedup, sourceRun);
  const enrichInput = latest.merge_dedup?.status === "completed" ? latest.merge_dedup : sourceRun;
  const enrichDone = Boolean(enrichInput && completedAfter(latest.profile_enrich, enrichInput));
  const rulesDone = enrichDone && completedAfter(latest.rules_filter, latest.profile_enrich);
  const similarityDone = rulesDone && completedAfter(latest.similarity_analyze, latest.rules_filter);
  const gradeDone = similarityDone && completedAfter(latest.ai_grade, latest.similarity_analyze);
  const phaseSteps = [
    { label: "Search", status: browser?.locked_search_url ? "done" : browser ? "current" : "pending" },
    { label: "Extract", status: extractDone ? "done" : browser?.locked_search_url ? "current" : "pending" },
    { label: "Merge", status: mergeDone ? "done" : extractDone ? "current" : "pending" },
    { label: "Enrich", status: enrichDone ? "done" : mergeDone ? "current" : "pending" },
    { label: "Rules", status: rulesDone ? "done" : enrichDone ? "current" : "pending" },
    { label: "Similarity", status: similarityDone ? "done" : rulesDone ? "current" : "pending" },
    { label: "AI grade", status: gradeDone ? "done" : similarityDone ? "current" : "pending" },
  ];
  let guide: { title: string; detail: string; action?: string; label?: string; stage?: StageType } = {
    title: "Prepare Sales Navigator search",
    detail: "Open AI search, confirm job filters, then lock exact search URL.",
    action: "browser",
    label: "Go to browser",
  };
  if (!activePipeline) {
    guide = mode === "sources"
      ? { title: "Start with a source", detail: "Choose Sales Navigator, Telegram, Apollo, or a file import. Each starts as its own dataset.", action: "sources", label: "Choose a source" }
      : { title: "Choose source datasets", detail: "Select one or more source datasets to combine or process.", action: "datasets", label: "Choose datasets" };
  } else if (rootType === "salesnav_extract" && !browser) {
    guide = { title: "Start embedded browser", detail: "Start browser, sign in once, then prepare Sales Navigator search.", action: "browser", label: "Go to browser" };
  } else if (rootType === "salesnav_extract" && !browser?.locked_search_url) {
    guide = { title: "Lock reviewed SalesNav search", detail: "Apply job filters, inspect results, then click Lock search.", action: "browser", label: "Go to browser" };
  } else if (rootType === "salesnav_extract" && !sourceRun) {
    guide = { title: `Extract ${salesnavLimit} SalesNav profiles`, detail: "Creates editable source dataset. No merge, enrichment, or grading starts automatically.", action: "run", label: `Start ${salesnavLimit}-profile extraction`, stage: "salesnav_extract" };
  } else if (rootType === "salesnav_extract" && sourceRun && ["pending", "running", "pause_requested"].includes(sourceRun.status)) {
    guide = { title: "Extraction running", detail: `Watch progress on Sales Navigator card. Pause finishes current profile; Stop now preserves flushed rows.` };
  } else if (rootType === "salesnav_extract" && sourceRun?.status === "paused") {
    guide = { title: "Extraction paused safely", detail: "Resume from saved checkpoint without duplicating current candidate.", action: "resume", label: "Resume extraction" };
  } else if (rootType === "salesnav_extract" && sourceRun?.status === "awaiting_auth") {
    guide = { title: "LinkedIn approval required", detail: "Complete challenge in embedded browser, then press Auth complete on Sales Navigator card.", action: "browser", label: "Go to browser" };
  } else if (sourceRun?.status === "awaiting_user") {
    const sourceLabel = CATALOG.find(item => item.type === sourceRun.stage_type)?.label || "source";
    guide = { title: `Review ${sourceLabel} candidates`, detail: "Open output dataset, inspect/edit/export. When satisfied, use Seal & continue on this source card.", action: "review", label: "Open source dataset", stage: sourceRun.stage_type };
  } else if (sourceRun && ["failed", "stopped"].includes(sourceRun.status)) {
    const canRerun = sourceRun.stage_type !== "telegram_extract" || Array.isArray(sourceRun.config.channels) && sourceRun.config.channels.length > 0;
    guide = canRerun
      ? { title: "Source run needs retry", detail: sourceRun.error || "Previous run stopped. Existing flushed rows remain available.", action: "rerun", label: "Rerun same setup" }
      : { title: "Telegram source needs setup", detail: "Choose channels, then start a new configured Telegram run.", action: "telegram-setup", label: "Configure Telegram" };
  } else {
    const downstream: StageType[] = ["merge_dedup", "profile_enrich", "rules_filter", "similarity_analyze", "ai_grade"];
    const nextType = downstream.find(type => {
      const currentRun = latest[type];
      const upstreamRun = type === "merge_dedup" ? sourceRun : latest[downstream[downstream.indexOf(type) - 1]];
      if (!currentRun || currentRun.status !== "completed") return true;
      return Boolean(upstreamRun?.created_at && currentRun.created_at && Date.parse(upstreamRun.created_at) > Date.parse(currentRun.created_at));
    });
    if (!nextType) {
      guide = { title: "Pipeline complete", detail: "Review graded dataset or export any earlier dataset version." };
    } else if (nextType === "merge_dedup" && selectedInputs.length === 0 && sourceRun?.output_dataset_id) {
      guide = { title: "Choose how to continue", detail: "Add another source and merge, or carry this source dataset forward by itself.", action: "source-only", label: "Use this source only" };
    } else if (nextType === "profile_enrich" && selectedInputs.length > 0 && !latest.profile_enrich) {
      guide = { title: "Enrichment is optional", detail: "Run deeper enrichment, or create a traceable pass-through version and continue without it.", action: "skip-enrich", label: "Skip enrichment" };
    } else if (latest[nextType]?.status === "awaiting_user") {
      guide = { title: `Review ${CATALOG.find(item => item.type === nextType)?.label} output`, detail: "Inspect/edit/export draft dataset. When satisfied, use Seal & continue on its stage card.", action: "review", label: "Open output dataset", stage: nextType };
    } else if (["pending", "running", "pause_requested"].includes(latest[nextType]?.status || "")) {
      guide = { title: `${CATALOG.find(item => item.type === nextType)?.label} running`, detail: "Watch stage-card progress. Pause or Stop now remains available.", stage: nextType };
    } else if (latest[nextType]?.status === "paused") {
      guide = { title: `${CATALOG.find(item => item.type === nextType)?.label} paused`, detail: "Resume from saved checkpoint.", action: "resume", label: "Resume stage", stage: nextType };
    } else if (latest[nextType] && ["failed", "stopped"].includes(latest[nextType]!.status)) {
      guide = { title: `${CATALOG.find(item => item.type === nextType)?.label} needs retry`, detail: latest[nextType]!.error || "Previous run stopped; flushed output remains available.", action: "rerun", label: "Rerun stage", stage: nextType };
    } else if (selectedInputs.length === 0) {
      guide = { title: `Choose input for ${CATALOG.find(item => item.type === nextType)?.label}`, detail: "Select one or more compatible datasets below. Then next-stage button becomes available.", action: "datasets", label: "Choose dataset", stage: nextType };
    } else {
      guide = { title: `Run ${CATALOG.find(item => item.type === nextType)?.label}`, detail: `${selectedInputs.length} dataset(s) selected. Stage will pause again for review.`, action: "run", label: `Start ${CATALOG.find(item => item.type === nextType)?.label}`, stage: nextType };
    }
  }
  if (mode === "pipeline") {
    const currentOutput = latest.ai_grade?.output_dataset_id || latest.similarity_analyze?.output_dataset_id || latest.rules_filter?.output_dataset_id || latest.profile_enrich?.output_dataset_id || latest.merge_dedup?.output_dataset_id;
    if (latest.ai_grade?.status === "awaiting_user" && currentOutput) {
      guide = { title: "Review grading output", detail: "Inspect, export, or approve the graded dataset when ready.", action: "review", label: "Inspect dataset", stage: "ai_grade" };
    } else if (selectedInputs.length === 0) {
      guide = { title: "Choose input datasets", detail: "Select approved or partial datasets below before merging or running an optional processing stage.", action: "datasets", label: "Choose datasets" };
    } else {
      guide = { title: "Merge selected datasets", detail: `${selectedInputs.length} dataset(s) selected. Merge creates a new reviewable version without changing the originals.`, action: "run", label: "Start merge & deduplicate", stage: "merge_dedup" };
    }
  }
  const executeGuide = async () => {
    const guideRun = guide.stage ? latest[guide.stage] : undefined;
    if (guide.action === "browser") { setShowBrowserWorkspace(true); setBrowserRequested(true); window.setTimeout(() => document.getElementById("browser-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0); }
    if (guide.action === "pipelines") document.getElementById("pipeline-selector")?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (guide.action === "sources") document.getElementById("source-start")?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (guide.action === "telegram-setup") document.getElementById("telegram-setup")?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (guide.action === "datasets") document.getElementById("datasets-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (guide.action === "run" && guide.stage) await run(guide.stage);
    if (guide.action === "resume" && guideRun) await control(guideRun, "resume");
    if (guide.action === "rerun" && guideRun) await control(guideRun, "rerun");
    if (guide.action === "review" && guideRun?.output_dataset_id) {
      setSelectedDataset(datasets.find(dataset => dataset.id === guideRun.output_dataset_id) || null);
      document.getElementById("datasets-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (guide.action === "source-only") { useOnlySource(); document.getElementById("datasets-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" }); }
    if (guide.action === "skip-enrich") await skipEnrichment();
  };
  const startSource = async (type: StageType) => {
    if (type === "telegram_extract") { setShowTelegramTools(true); document.getElementById("telegram-setup")?.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
    if (type === "salesnav_extract") { setShowBrowserWorkspace(true); setBrowserRequested(true); window.setTimeout(() => document.getElementById("browser-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0); return; }
    await run(type);
  };
  const showSources = mode === "sources";
  const showPipeline = mode === "pipeline";
  const showDatasets = mode === "datasets";
  const latestSource = Object.fromEntries(
    CATALOG.filter(definition => definition.source).map(definition => [definition.type, stages.filter(stage => stage.stage_type === definition.type).at(-1)]),
  ) as Partial<Record<StageType, StageRun>>;
  return <div className="space-y-5">
    {error && <div className="p-3 rounded border border-red-500/40 bg-red-500/10 text-red-300">{error}</div>}
    {showSources && <div id="source-start" className="rounded-xl border border-[var(--accent)]/40 bg-[var(--panel)] p-4"><div className="text-[10px] uppercase tracking-widest text-[var(--accent)]">Start with a source</div><div className="text-sm text-[var(--muted)] mt-1">Every source creates an independent dataset. Combine only the datasets you choose later.</div><div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">{CATALOG.filter(definition => definition.source).map(definition => <button key={definition.type} onClick={() => startSource(definition.type).catch(nextError => setError(nextError.message))} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-3 text-left hover:border-[var(--accent)]"><span className="material-symbols-outlined text-[18px] text-[var(--accent)] align-middle mr-2">{definition.icon}</span><span className="text-sm font-medium text-[var(--fg)]">{definition.label}</span><div className="text-[11px] text-[var(--muted)] mt-1">{definition.type === "salesnav_extract" ? "Set up a search" : definition.type === "telegram_extract" ? "Find channels" : definition.type === "file_import" ? "Upload data" : "Configure source"}</div></button>)}</div></div>}
    {(showSources || showPipeline) && <div className="sticky top-3 z-20 rounded-xl border border-[var(--accent)]/50 bg-[var(--surface)]/95 backdrop-blur p-4 shadow-lg">
      <div className="text-[10px] uppercase tracking-widest text-[var(--accent)] mb-2">Next action</div>
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-64"><div className="font-semibold text-[var(--fg)]">{guide.title}</div><div className="text-sm text-[var(--muted)] mt-1">{guide.detail}</div></div>
        {guide.action && <button onClick={() => executeGuide().catch(nextError => setError(nextError.message))} className="btn-primary px-4 py-2">{guide.label}</button>}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2 mt-4">
        {phaseSteps.map((step, index) => <div key={step.label} className={`rounded-lg border px-3 py-2 text-xs ${step.status === "done" ? "border-green-500/40 bg-green-500/10 text-green-300" : step.status === "current" ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--fg)]" : "border-[var(--border)] text-[var(--muted)]"}`}><span className="mr-1">{step.status === "done" ? "✓" : index + 1}.</span>{step.label}</div>)}
      </div>
    </div>}
    {showSources && showBrowserWorkspace && <BrowserPanel jobId={jobId} session={browser} onSession={setBrowser} openRequested={browserRequested} onOpenHandled={() => setBrowserRequested(false)} />}
    {(showSources || showPipeline) && <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"><div className="flex flex-wrap items-center justify-between gap-3 mb-3"><div><h2 className="font-semibold text-[var(--fg)]">{showSources ? "Source runs" : "Combined pipeline"}</h2><p className="text-xs text-[var(--muted)]">{showSources ? "Set up, extract, then review each source independently." : "Choose datasets below, then run only the stages you need."}</p></div>{showSources && <div className="flex items-center gap-2"><label className="text-xs text-[var(--muted)]">SalesNav profiles <input type="number" min={1} max={200} value={salesnavLimit} onChange={event => setSalesnavLimit(Math.max(1, Math.min(200, Number(event.target.value) || 1)))} className="input ml-1 w-20 text-sm" /></label><button onClick={() => fileRef.current?.click()} className="btn-secondary text-xs px-3 py-1.5">Import dataset</button></div>}</div>
      <input ref={fileRef} className="hidden" type="file" accept=".xlsx,.xls,.csv,.json" onChange={e => e.target.files?.[0] && upload(e.target.files[0]).catch(err => setError(err.message))} />
      {showSources && <div id="telegram-setup" className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--panel)] p-3"><button onClick={() => setShowTelegramTools(value => !value)} className="w-full flex items-center justify-between text-left"><span><span className="font-medium text-[var(--fg)]">Telegram source tools</span><span className="text-xs text-[var(--muted)] ml-2">Search channels and start a new Telegram pipeline</span></span><span className="text-[var(--accent)] text-xs">{showTelegramTools ? "Hide" : "Open"}</span></button>{showTelegramTools && <div className="mt-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-sm font-medium text-[var(--fg)]">Start Telegram extraction</div><div className="text-xs text-[var(--muted)] mt-1">1. Search channels. 2. Click <b>+ Add</b>. 3. Start bounded scan.</div></div><button disabled={selectedTelegramChannels.length === 0} onClick={() => run("telegram_extract").catch(nextError => setError(nextError.message))} className="btn-primary text-sm px-4 py-2 disabled:opacity-40">Start Telegram scan · {selectedTelegramChannels.length} channel{selectedTelegramChannels.length === 1 ? "" : "s"}</button></div><div className="flex gap-2 mt-3"><input value={telegramQuery} onChange={event => setTelegramQuery(event.target.value)} onKeyDown={event => event.key === "Enter" && findTelegramChannels()} placeholder="Search Telegram channels, e.g. python jobs" className="input text-sm flex-1" /><button disabled={telegramSearching || telegramQuery.trim().length < 2} onClick={() => findTelegramChannels()} className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-40">{telegramSearching ? "Searching…" : "Find channels"}</button></div>{telegramMatches.length > 0 && <div className="mt-3"><div className="text-xs text-[var(--muted)] mb-2">Search results — click + Add</div><div className="flex flex-wrap gap-2">{telegramMatches.map(match => <button key={match.handle} onClick={() => addTelegramChannel(match.handle)} className="rounded border border-[var(--border)] px-2 py-1 text-xs hover:border-[var(--accent)]"><span className="text-[var(--accent)]">+ Add</span><span className="text-[var(--fg)]"> · {match.title}</span><span className="text-[var(--muted)]"> · {match.handle}</span></button>)}</div></div>}<div className="mt-3"><div className="text-xs text-[var(--muted)] mb-2">Chosen channels</div>{selectedTelegramChannels.length ? <div className="flex flex-wrap gap-2">{selectedTelegramChannels.map(handle => <button key={handle} onClick={() => removeTelegramChannel(handle)} className="rounded bg-[var(--accent)]/10 border border-[var(--accent)]/40 px-2 py-1 text-xs text-[var(--fg)]">{handle} ×</button>)}</div> : <div className="text-xs text-[var(--muted)]">None yet — add one or more search results.</div>}</div><div className="grid md:grid-cols-4 gap-2 mt-3"><input value={telegramChannels} onChange={event => setTelegramChannels(event.target.value)} placeholder="Or paste @channel handles" className="input text-sm md:col-span-2" /><input value={telegramKeywords} onChange={event => setTelegramKeywords(event.target.value)} placeholder="Candidate keywords" className="input text-sm" /><label className="text-xs text-[var(--muted)] flex items-center gap-2">Last <input type="number" min={1} max={365} value={telegramDays} onChange={event => setTelegramDays(Number(event.target.value) || 30)} className="input w-16 text-sm" /> days</label><label className="text-xs text-[var(--muted)] flex items-center gap-2">Max/channel <input type="number" min={10} max={1000} value={telegramLimit} onChange={event => setTelegramLimit(Number(event.target.value) || 100)} className="input w-16 text-sm" /></label></div></div>}</div>}
      <div className="space-y-3">{(showSources ? [["Source providers", CATALOG.filter(def => def.source)]] : [["Combine", CATALOG.filter(def => def.phase === 2)], ["Optional processing", CATALOG.filter(def => def.phase >= 3)]]).map(([title, definitions], index) => <details key={String(title)} open={index === 0} className="rounded-lg border border-[var(--border)] bg-[var(--panel)] p-3"><summary className="cursor-pointer text-xs uppercase tracking-widest text-[var(--muted)]">{String(title)}</summary><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 mt-3">{(definitions as typeof CATALOG).map(def => <StageCard key={def.type} definition={def} run={showSources ? latestSource[def.type] : latest[def.type]} selectedInputs={selectedInputs} onRun={() => run(def.type).catch(e => setError(e.message))} onControl={action => (showSources ? latestSource[def.type] : latest[def.type]) && control((showSources ? latestSource[def.type] : latest[def.type])!, action).catch(e => setError(e.message))} onSelectOutput={() => { const id = (showSources ? latestSource[def.type] : latest[def.type])?.output_dataset_id; setSelectedDataset(datasets.find(d => d.id === id) || null); }} />)}</div></details>)}</div>
    </div>}
    {(showPipeline || showDatasets) && <details id="datasets-workspace" open={showDatasets} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"><summary className="cursor-pointer list-none flex items-center justify-between gap-3"><span><span className="font-medium text-[var(--fg)]">Datasets</span><span className="text-xs text-[var(--muted)] ml-2">{datasets.length} versions · select inputs when needed</span></span><span className="text-xs text-[var(--accent)]">{showDatasets ? "Open" : "Choose inputs"}</span></summary><div className="text-xs text-[var(--muted)] mt-3 mb-3">Grouped by run. Draft data can be edited; approved versions stay unchanged.</div><div className="space-y-5">{pipelines.map(pipeline => { const pipelineDatasetIds = new Set(pipeline.runs.map(stage => stage.output_dataset_id).filter(Boolean)); const groupedDatasets = datasets.filter(dataset => pipelineDatasetIds.has(dataset.id)); if (!groupedDatasets.length) return null; return <section key={pipeline.id} className={`rounded-lg border p-3 ${activePipeline?.id === pipeline.id ? "border-[var(--accent)]/50" : "border-[var(--border)]"}`}><div className="flex items-center justify-between gap-3 mb-2"><button onClick={() => { setActivePipelineId(pipeline.id); setSelectedInputs([]); }} className="text-left"><div className="text-sm font-medium text-[var(--fg)]">{pipeline.label}</div><div className="text-xs text-[var(--muted)]">Created {formatTime(pipeline.createdAt)} · {pipeline.runs.length} stage runs</div></button>{activePipeline?.id === pipeline.id && <span className="text-[10px] text-[var(--accent)] uppercase">Selected</span>}</div><div className="space-y-2">{groupedDatasets.map(dataset => { const stage = runForDataset.get(dataset.id); return <div key={dataset.id} className={`rounded border p-2 ${selectedInputs.includes(dataset.id) ? "border-[var(--accent)] bg-[var(--accent)]/10" : "border-[var(--border)]"}`}><div className="flex flex-wrap items-center gap-x-3 gap-y-2"><label className="flex items-center gap-2 text-xs cursor-pointer"><input type="checkbox" checked={selectedInputs.includes(dataset.id)} onChange={e => setSelectedInputs(e.target.checked ? [...selectedInputs, dataset.id] : selectedInputs.filter(id => id !== dataset.id))} /><span className="font-medium text-[var(--fg)]">{CATALOG.find(item => item.type === stage?.stage_type)?.label || dataset.kind} · run {stage?.attempt || 1}</span></label><span className="text-xs text-[var(--muted)]">{formatTime(stage?.created_at || dataset.created_at)}{duration(stage) ? ` · ${duration(stage)}` : ""} · {dataset.row_count} rows · {datasetStateLabel(dataset)}</span><button type="button" onClick={() => setSelectedDataset(dataset)} className="ml-auto text-xs text-[var(--accent)] hover:underline">Inspect</button></div><div className="text-[11px] text-[var(--muted)] mt-1">{dataset.name} · created from {stage ? CATALOG.find(item => item.type === stage.stage_type)?.label : "import"}</div></div>; })}</div></section>; })}</div></details>}
    {(showDatasets || selectedDataset) && selectedDataset && <DatasetGate dataset={selectedDataset} onChanged={next => { if (next) setSelectedDataset(next); load(); }} />}
  </div>;
}
