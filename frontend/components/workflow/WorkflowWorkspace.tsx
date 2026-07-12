"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWebSocket } from "@/lib/hooks/useWebSocket";
import {
  BrowserSession, CandidateDataset, CandidateRecord, StageRun, StageType,
  browserCommand, controlStage, createBrowserSession, createStage, deleteRecord, downloadDataset,
  getJobBrowserSession, getRecords, importDataset, listDatasets, listStages, patchRecord, previewImport,
} from "@/lib/workflow";

const CATALOG: Array<{ type: StageType; label: string; icon: string; source?: boolean; requires?: string }> = [
  { type: "salesnav_extract", label: "Sales Navigator", icon: "travel_explore", source: true },
  { type: "telegram_extract", label: "Telegram", icon: "send", source: true },
  { type: "apollo_extract", label: "Apollo", icon: "person_search", source: true },
  { type: "file_import", label: "File Import", icon: "upload_file", source: true },
  { type: "merge_dedup", label: "Merge & Dedup", icon: "merge", requires: "Select source datasets" },
  { type: "profile_enrich", label: "Enrich Profiles", icon: "manage_search", requires: "Select normalized dataset" },
  { type: "rules_filter", label: "Rules Filter", icon: "rule", requires: "Select normalized dataset" },
  { type: "similarity_analyze", label: "Similarity", icon: "analytics", requires: "Select normalized dataset" },
  { type: "ai_grade", label: "AI Grade", icon: "star", requires: "Select normalized dataset" },
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
  const pct = run?.progress?.percentage || 0;
  return (
    <div className={`rounded-xl border bg-[var(--panel)] p-4 ${run ? STATUS_COLORS[run.status] || "border-[var(--border)]" : "border-[var(--border)]"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex gap-3">
          <span className="material-symbols-outlined text-[22px] text-[var(--accent)]">{definition.icon}</span>
          <div>
            <div className="font-medium text-[var(--fg)]">{definition.label}</div>
            <div className="text-xs text-[var(--muted)] mt-0.5">{run ? `${run.status} · attempt ${run.attempt}` : definition.requires || "Independent source tool"}</div>
          </div>
        </div>
        {run?.output_dataset_id && <button onClick={onSelectOutput} className="text-xs text-[var(--accent)] hover:underline">Open data</button>}
      </div>
      {run && (run.status === "running" || run.status === "pause_requested") && (
        <div className="mt-3"><div className="h-1.5 rounded bg-[var(--panel2)] overflow-hidden"><div className="h-full bg-[var(--accent)]" style={{ width: `${pct}%` }} /></div><div className="text-[10px] text-[var(--muted)] mt-1">{run.progress.current || 0}/{run.progress.total || "?"}</div></div>
      )}
      {run?.error && <div className="mt-2 text-xs text-red-400 line-clamp-2">{run.error}</div>}
      <div className="flex flex-wrap gap-2 mt-4">
        {!active && run?.status !== "awaiting_user" && <button onClick={onRun} disabled={!definition.source && selectedInputs.length === 0} className="btn-primary text-xs px-3 py-1.5 disabled:opacity-40">{run ? "New run" : "Start"}</button>}
        {run?.status === "running" && <button onClick={() => onControl("pause")} className="btn-secondary text-xs px-3 py-1.5">Pause</button>}
        {run?.status === "paused" && <button onClick={() => onControl("resume")} className="btn-primary text-xs px-3 py-1.5">Resume</button>}
        {run?.status === "awaiting_auth" && <button onClick={() => onControl("resume")} className="btn-primary text-xs px-3 py-1.5">Auth complete</button>}
        {active && <button onClick={() => onControl("stop")} className="text-xs px-3 py-1.5 rounded border border-red-500/50 text-red-400">Stop now</button>}
        {run?.status === "awaiting_user" && <button onClick={() => onControl("continue")} className="btn-primary text-xs px-3 py-1.5">Seal & continue</button>}
        {run && ["completed", "failed", "stopped", "skipped"].includes(run.status) && <button onClick={() => onControl("rerun")} className="btn-secondary text-xs px-3 py-1.5">Rerun</button>}
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
        <div className="flex-1 min-w-52"><div className="font-medium text-[var(--fg)]">{dataset.name}</div><div className="text-xs text-[var(--muted)]">{dataset.kind} · {dataset.state} · {dataset.row_count} rows · v{dataset.id.slice(0, 8)}</div></div>
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
      <div className="px-4 py-2 text-[10px] text-[var(--muted)] border-t border-[var(--border)]">Double-click name, headline, or location to edit. Editing sealed data creates a new child version.</div>
    </div>
  );
}

function BrowserPanel({ jobId, session, onSession }: { jobId: string; session: BrowserSession | null; onSession: (s: BrowserSession) => void }) {
  const [busy, setBusy] = useState(false);
  const command = async (action: "open-search" | "lock-search" | "take-control" | "release-control") => {
    if (!session) return;
    setBusy(true); try { onSession(await browserCommand(session.id, action)); } finally { setBusy(false); }
  };
  const start = async () => { setBusy(true); try { onSession(await createBrowserSession(jobId)); } finally { setBusy(false); } };
  return <div className="rounded-xl border border-[var(--border)] bg-[var(--panel)] overflow-hidden">
    <div className="p-4 flex flex-wrap items-center gap-2 border-b border-[var(--border)]"><div className="flex-1"><div className="font-medium text-[var(--fg)]">Interactive Sales Navigator</div><div className="text-xs text-[var(--muted)]">{session?.state || "Browser stopped"}{session?.current_url ? ` · ${session.current_url}` : ""}</div></div>
      {!session && <button disabled={busy} onClick={start} className="btn-primary text-xs px-3 py-1.5">Start browser</button>}
      {session && <><button disabled={busy} onClick={() => command("open-search")} className="btn-secondary text-xs px-3 py-1.5">Open AI search</button><button disabled={busy} onClick={() => command("lock-search")} className="btn-primary text-xs px-3 py-1.5">Lock search</button><button disabled={busy} onClick={() => command("take-control")} className="btn-secondary text-xs px-3 py-1.5">Take control</button><button disabled={busy} onClick={() => command("release-control")} className="btn-secondary text-xs px-3 py-1.5">Release</button></>}
    </div>
    {session?.state === "awaiting_auth" && <div className="p-3 bg-orange-500/10 text-orange-300 border-b border-orange-500/30">LinkedIn needs login or mobile approval. Complete it in browser, then lock search.</div>}
    {session?.viewer_url ? <iframe title="Sales Navigator browser" src={session.viewer_url} className="w-full h-[620px] bg-black" allow="clipboard-read; clipboard-write" /> : <div className="h-48 grid place-items-center text-[var(--muted)]">Start browser to open embedded noVNC viewer.</div>}
  </div>;
}

export function WorkflowWorkspace({ jobId }: { jobId: string }) {
  const [stages, setStages] = useState<StageRun[]>([]);
  const [datasets, setDatasets] = useState<CandidateDataset[]>([]);
  const [selectedInputs, setSelectedInputs] = useState<string[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<CandidateDataset | null>(null);
  const [browser, setBrowser] = useState<BrowserSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: event } = useWebSocket<any>(`/ws/jobs/${jobId}`);
  const load = useCallback(async () => {
    const [nextStages, nextDatasets, nextBrowser] = await Promise.all([listStages(jobId), listDatasets(jobId), getJobBrowserSession(jobId)]);
    setStages(nextStages); setDatasets(nextDatasets);
    if (nextBrowser) setBrowser(nextBrowser);
    if (selectedDataset) setSelectedDataset(nextDatasets.find(d => d.id === selectedDataset.id) || selectedDataset);
  }, [jobId, selectedDataset]);
  useEffect(() => { load().catch(e => setError(e.message)); }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!event) return; load(); if (event.type === "browser.auth_required") { try { const context = new AudioContext(); const oscillator = context.createOscillator(); oscillator.connect(context.destination); oscillator.start(); oscillator.stop(context.currentTime + 0.2); new Notification("Sourcer needs LinkedIn approval", { body: "Complete login in embedded browser." }); } catch {} } }, [event]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (typeof Notification !== "undefined" && Notification.permission === "default") Notification.requestPermission(); }, []);

  const latest = useMemo(() => Object.fromEntries(CATALOG.map(item => [item.type, stages.filter(s => s.stage_type === item.type).at(-1)])), [stages]);
  const run = async (type: StageType) => {
    if (type === "file_import") { fileRef.current?.click(); return; }
    const config: Record<string, unknown> = {};
    if (type === "salesnav_extract") {
      if (!browser?.id || !browser.locked_search_url) throw new Error("Start browser and lock Sales Navigator search first");
      config.browser_session_id = browser.id;
    }
    if (type === "profile_enrich") {
      config.provider = browser?.id ? "local" : "apify";
      if (browser?.id) config.browser_session_id = browser.id;
    }
    await createStage(jobId, { stage_type: type, input_dataset_ids: CATALOG.find(v => v.type === type)?.source ? [] : selectedInputs, config });
    await load();
  };
  const control = async (run: StageRun, action: "pause" | "resume" | "stop" | "skip" | "rerun" | "continue") => { await controlStage(run.id, action); await load(); };
  const upload = async (file: File) => {
    const preview = await previewImport(file);
    if (!confirm(`Import ${preview.row_count} rows with ${preview.columns.length} detected columns?`)) return;
    const dataset = await importDataset(jobId, file); await load(); setSelectedDataset(dataset);
  };
  return <div className="space-y-5">
    {error && <div className="p-3 rounded border border-red-500/40 bg-red-500/10 text-red-300">{error}</div>}
    <BrowserPanel jobId={jobId} session={browser} onSession={setBrowser} />
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"><div className="flex items-center justify-between mb-3"><div><h2 className="font-semibold text-[var(--fg)]">Stage workspace</h2><p className="text-xs text-[var(--muted)]">Every stage pauses at output gate. Select sealed or partial datasets as next inputs.</p></div><button onClick={() => fileRef.current?.click()} className="btn-secondary text-xs px-3 py-1.5">Import dataset</button></div>
      <input ref={fileRef} className="hidden" type="file" accept=".xlsx,.xls,.csv,.json" onChange={e => e.target.files?.[0] && upload(e.target.files[0]).catch(err => setError(err.message))} />
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">{CATALOG.map(def => <StageCard key={def.type} definition={def} run={latest[def.type]} selectedInputs={selectedInputs} onRun={() => run(def.type).catch(e => setError(e.message))} onControl={action => latest[def.type] && control(latest[def.type]!, action).catch(e => setError(e.message))} onSelectOutput={() => { const id = latest[def.type]?.output_dataset_id; setSelectedDataset(datasets.find(d => d.id === id) || null); }} />)}</div>
    </div>
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"><div className="font-medium text-[var(--fg)] mb-3">Available datasets</div><div className="flex flex-wrap gap-2">{datasets.map(dataset => <label key={dataset.id} className={`px-3 py-2 rounded-lg border cursor-pointer text-xs ${selectedInputs.includes(dataset.id) ? "border-[var(--accent)] bg-[var(--accent)]/10" : "border-[var(--border)]"}`}><input className="mr-2" type="checkbox" checked={selectedInputs.includes(dataset.id)} onChange={e => setSelectedInputs(e.target.checked ? [...selectedInputs, dataset.id] : selectedInputs.filter(id => id !== dataset.id))} /><button type="button" onClick={() => setSelectedDataset(dataset)} className="text-left">{dataset.name} · {dataset.row_count} · {dataset.state}</button></label>)}</div></div>
    {selectedDataset && <DatasetGate dataset={selectedDataset} onChanged={next => { if (next) setSelectedDataset(next); load(); }} />}
  </div>;
}
