"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, setCampaignMode, updateCampaign, deleteCampaign, deleteLead, sendReply, type Campaign, type Lead, type Message } from "@/lib/api";
import { Badge, Btn, Card, StatCard, Toggle, inputCls, Spinner } from "@/components/ui";
import { intentColor } from "@/lib/intent";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Play, Download, Search, ExternalLink, Bot, ChevronRight, Trash2, Pause, Send, Inbox } from "lucide-react";

type ExtendedLead = Lead & { score?: number };

const KANBAN_COLS: { key: string; label: string; color: string }[] = [
  { key: "pending",   label: "Pending",    color: "text-amber-400"  },
  { key: "sent",      label: "Sent",       color: "text-blue-400"   },
  { key: "replied",   label: "Replied",    color: "text-purple-400" },
  { key: "qualified", label: "Qualified",  color: "text-green-400"  },
  { key: "rejected",  label: "Rejected",   color: "text-red-400"    },
  { key: "skipped",   label: "Skipped",    color: "text-[var(--muted)]" },
];

function exportCSV(leads: ExtendedLead[], campaignName: string) {
  const cols = ["full_name", "headline", "source", "score", "status", "ai_intent",
    "telegram_url", "linkedin_url", "last_message"];
  const header = cols.join(",");
  const rows = leads.map((l) =>
    cols.map((c) => {
      const val = (l as Record<string, unknown>)[c];
      if (val == null) return "";
      return `"${String(val).replace(/"/g, '""')}"`;
    }).join(",")
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${campaignName.replace(/\s+/g, "_")}_leads.csv`;
  a.click();
}

type View = "table" | "kanban";

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [campaign, setCampaign]     = useState<Campaign | null>(null);
  const [leads, setLeads]           = useState<ExtendedLead[]>([]);
  const [view, setView]             = useState<View>("kanban");
  const [search, setSearch]         = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [starting, setStarting]     = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [modeLoading, setModeLoading] = useState(false);
  const [deleting, setDeleting]     = useState(false);
  const [pausing, setPausing]       = useState(false);

  const [slideLead, setSlideLead]   = useState<ExtendedLead | null>(null);
  const [thread, setThread]         = useState<Message[]>([]);
  const [threadLoading, setThreadLoading] = useState(false);
  const [slideReply, setSlideReply] = useState("");
  const [slideChannel, setSlideChannel] = useState<"telegram" | "linkedin">("telegram");
  const [slideSending, setSlideSending] = useState(false);

  const load = useCallback(async () => {
    const q = new URLSearchParams();
    if (statusFilter) q.set("status", statusFilter);
    const [c, ls] = await Promise.all([
      apiFetch<Campaign>(`/outreach/campaigns/${params.id}`).catch(() => null),
      apiFetch<ExtendedLead[]>(`/outreach/campaigns/${params.id}/leads?${q}`).catch(() => []),
    ]);
    setCampaign(c);
    setLeads(ls);
  }, [params.id, statusFilter]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 6000);
    return () => clearInterval(iv);
  }, [load]);

  const openThread = useCallback(async (lead: ExtendedLead) => {
    setSlideLead(lead);
    setThreadLoading(true);
    const msgs = await apiFetch<Message[]>(`/outreach/conversations/${lead.id}/messages`).catch(() => []);
    setThread(msgs);
    setThreadLoading(false);
  }, []);

  const patchLead = useCallback(async (leadId: string, status: string) => {
    setActionLoading(leadId + status);
    await apiFetch(`/outreach/leads/${leadId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }).catch(() => {});
    setActionLoading(null);
    load();
  }, [load]);

  const sendNow = useCallback(async (leadId: string) => {
    setActionLoading(leadId + "send");
    try {
      await apiFetch(`/outreach/leads/${leadId}/send`, {
        method: "POST",
        body: JSON.stringify({}),
      });
    } catch (e) {
      console.error("sendNow failed:", e);
    }
    setActionLoading(null);
    load();
  }, [load]);

  const startCampaign = useCallback(async () => {
    setStarting(true);
    await apiFetch(`/outreach/campaigns/${params.id}/start`, { method: "POST" }).catch(() => {});
    setStarting(false);
    load();
  }, [params.id, load]);

  const toggleMode = useCallback(async () => {
    if (!campaign) return;
    const next = campaign.outreach_mode === "autopilot" ? "copilot" : "autopilot";
    setModeLoading(true);
    await setCampaignMode(params.id, next).catch(() => {});
    setCampaign((c) => c ? { ...c, outreach_mode: next } : c);
    setModeLoading(false);
  }, [campaign, params.id]);

  const handleDelete = useCallback(async () => {
    if (!campaign) return;
    if (!confirm(`Delete campaign "${campaign.name}" and all its leads? This cannot be undone.`)) return;
    setDeleting(true);
    await deleteCampaign(params.id).catch(() => {});
    router.push("/outreach");
  }, [campaign, params.id, router]);

  const handleTogglePause = useCallback(async () => {
    if (!campaign) return;
    const next = campaign.status === "paused" ? "active" : "paused";
    setPausing(true);
    await updateCampaign(params.id, { status: next }).catch(() => {});
    setCampaign((c) => c ? { ...c, status: next } : c);
    setPausing(false);
  }, [campaign, params.id]);

  const handleDeleteLead = useCallback(async (leadId: string, name: string) => {
    if (!confirm(`Remove "${name}" from this campaign?`)) return;
    setActionLoading(leadId + "del");
    await deleteLead(leadId).catch(() => {});
    setActionLoading(null);
    load();
  }, [load]);

  const doSlideReply = useCallback(async () => {
    if (!slideLead || !slideReply.trim()) return;
    setSlideSending(true);
    await sendReply(slideLead.id, slideReply.trim(), slideChannel).catch(() => {});
    setSlideReply("");
    setSlideSending(false);
    const msgs = await apiFetch<Message[]>(`/outreach/conversations/${slideLead.id}/messages`).catch(() => []);
    setThread(msgs);
    load();
  }, [slideLead, slideReply, slideChannel, load]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return leads.filter((l) => !q || (l.full_name ?? "").toLowerCase().includes(q));
  }, [leads, search]);

  const byStatus = useMemo(() => {
    const map: Record<string, ExtendedLead[]> = {};
    KANBAN_COLS.forEach(({ key }) => { map[key] = []; });
    filtered.forEach((l) => {
      const bucket = map[l.status];
      if (bucket) bucket.push(l);
      else (map["skipped"] ??= []).push(l);
    });
    return map;
  }, [filtered]);

  const stats = (campaign as Record<string, unknown>)?.stats as Record<string, number> | undefined;

  const isAutopilot = campaign?.outreach_mode === "autopilot";

  return (
    <div className="grid gap-5">
      {/* Breadcrumb + header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm text-[var(--muted)] mb-1">
            <Link href="/outreach" className="hover:text-[var(--fg)]">Campaigns</Link>
            <ChevronRight size={14} />
            <span>{campaign?.name ?? "…"}</span>
          </div>
          <h1 className="text-xl font-semibold">{campaign?.name ?? "…"}</h1>
          <div className="flex items-center gap-3 mt-1">
            {campaign?.status && (
              <Badge variant={(campaign.status as "active" | "draft" | "pending" | "default")}>
                {campaign.status}
                {campaign.status === "active" && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 pulse-dot" />
                )}
              </Badge>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          {/* Copilot / Autopilot toggle */}
          <div className="flex items-center gap-2 bg-[var(--panel)] border border-[var(--border)] rounded-lg px-3 py-2">
            <Bot size={14} className={isAutopilot ? "text-purple-400" : "text-[var(--muted)]"} />
            <span className="text-xs text-[var(--fg2)]">
              {isAutopilot ? "Autopilot" : "Copilot"}
            </span>
            {modeLoading ? <Spinner size="sm" /> : (
              <Toggle
                checked={isAutopilot}
                onChange={toggleMode}
              />
            )}
          </div>

          <Link href="/outreach/inbox">
            <Btn variant="ghost" size="sm">
              <Inbox size={13} />
              Inbox
            </Btn>
          </Link>

          <Btn
            variant="secondary"
            size="sm"
            onClick={() => exportCSV(leads, campaign?.name ?? "campaign")}
          >
            <Download size={13} />
            Export CSV
          </Btn>

          {campaign && (campaign.status === "active" || campaign.status === "paused") && (
            <Btn
              variant="ghost"
              size="sm"
              loading={pausing}
              onClick={handleTogglePause}
            >
              <Pause size={13} />
              {campaign.status === "paused" ? "Resume" : "Pause"}
            </Btn>
          )}

          <Btn
            variant="primary"
            loading={starting}
            disabled={campaign?.status === "done"}
            onClick={startCampaign}
          >
            <Play size={13} />
            Start campaign
          </Btn>

          <Btn
            variant="danger"
            size="sm"
            loading={deleting}
            onClick={handleDelete}
          >
            <Trash2 size={13} />
          </Btn>
        </div>
      </div>

      {/* Mode info banner */}
      {campaign && (
        <div className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm border ${
          isAutopilot
            ? "bg-purple-900/20 border-purple-800/40 text-purple-300"
            : "bg-blue-900/10 border-blue-800/30 text-blue-300"
        }`}>
          <Bot size={15} />
          {isAutopilot
            ? "🤖 Autopilot mode — AI replies are sent automatically. Declined/ambiguous messages always go to Copilot for review."
            : "👁 Copilot mode — AI drafts replies but waits for your approval before sending. Check the Review Queue."}
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {[
            { label: "Total",     val: stats.total,     color: "default" },
            { label: "Pending",   val: stats.pending,   color: "amber"   },
            { label: "Sent",      val: stats.sent,      color: "blue"    },
            { label: "Replied",   val: stats.replied,   color: "purple"  },
            { label: "Qualified", val: stats.qualified, color: "green"   },
            { label: "Rejected",  val: stats.rejected,  color: "default" },
          ].map(({ label, val, color }) => (
            <StatCard key={label} label={label} value={val ?? 0} color={color as "default" | "green" | "blue" | "purple" | "amber"} />
          ))}
        </div>
      )}

      {/* View toggle + search */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
          {(["table", "kanban"] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                view === v
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--panel2)] text-[var(--muted)] hover:text-[var(--fg)]"
              }`}
            >
              {v}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            className={inputCls + " pl-7 w-48 h-8 text-xs"}
            placeholder="Search leads…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {view === "table" && (
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[var(--bg2)] border border-[var(--border)] rounded-lg px-2 py-1.5 text-xs focus:outline-none h-8"
          >
            <option value="">All statuses</option>
            {KANBAN_COLS.map(({ key, label }) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        )}

        <span className="text-xs text-[var(--muted)] ml-auto">
          {filtered.length} lead{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* KANBAN VIEW */}
      {view === "kanban" && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {KANBAN_COLS.map(({ key, label, color }) => (
            <div key={key} className="flex flex-col gap-2">
              <div className="flex items-center justify-between px-1">
                <span className={`text-xs font-semibold uppercase tracking-wider ${color}`}>{label}</span>
                <span className="text-xs text-[var(--muted)]">{byStatus[key]?.length ?? 0}</span>
              </div>
              <div className="flex flex-col gap-2 min-h-[100px]">
                {(byStatus[key] ?? []).map((lead) => (
                  <Card
                    key={lead.id}
                    className="p-3 cursor-pointer"
                    onClick={() => openThread(lead)}
                  >
                    <div className="text-xs font-medium text-[var(--fg)] truncate">
                      {lead.full_name ?? "—"}
                    </div>
                    {lead.headline && (
                      <div className="text-[10px] text-[var(--muted)] truncate mt-0.5">
                        {lead.headline}
                      </div>
                    )}
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      {lead.score != null && (
                        <span className="text-[10px] font-mono text-[var(--accent)]">{lead.score}</span>
                      )}
                      {lead.ai_intent && (
                        <span className={`text-[10px] ${intentColor[lead.ai_intent] ?? ""}`}>
                          {lead.ai_intent}
                        </span>
                      )}
                      {lead.needs_review && (
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" title="Needs review" />
                      )}
                    </div>
                    {lead.status === "pending" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); sendNow(lead.id); }}
                        className="mt-2 w-full text-[10px] py-1 rounded bg-[var(--accent)]/15 text-[var(--accent)] hover:bg-[var(--accent)]/25 transition-colors"
                      >
                        {actionLoading === lead.id + "send" ? "…" : "Send now"}
                      </button>
                    )}
                  </Card>
                ))}
                {(byStatus[key] ?? []).length === 0 && (
                  <div className="text-[10px] text-[var(--muted)] text-center py-4 border border-dashed border-[var(--border)] rounded-xl">
                    Empty
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TABLE VIEW */}
      {view === "table" && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--panel2)]">
                  {["Name", "Headline", "Source", "Score", "Status", "Intent", "Links", "Actions"].map((h) => (
                    <th key={h} className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((lead) => (
                  <tr key={lead.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--panel2)] transition-colors">
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => openThread(lead)}
                        className="font-medium text-[var(--accent)] hover:underline text-left"
                      >
                        {lead.full_name ?? "—"}
                      </button>
                    </td>
                    <td className="px-3 py-2.5 max-w-[180px]">
                      <span className="truncate block text-[var(--muted)] text-xs">{lead.headline ?? "—"}</span>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-[var(--muted)]">{lead.source ?? "—"}</td>
                    <td className="px-3 py-2.5 font-mono text-xs text-[var(--accent)]">{lead.score ?? "—"}</td>
                    <td className="px-3 py-2.5">
                      <Badge variant={lead.status as "pending" | "sent" | "replied" | "qualified" | "rejected"}>
                        {lead.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5">
                      {lead.ai_intent ? (
                        <span className={`text-xs ${intentColor[lead.ai_intent] ?? ""}`}>{lead.ai_intent}</span>
                      ) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-xs">
                      <div className="flex gap-2">
                        {lead.linkedin_url && (
                          <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="text-[var(--accent)] hover:underline flex items-center gap-0.5">
                            LI<ExternalLink size={10} />
                          </a>
                        )}
                        {lead.telegram_url && (
                          <a href={lead.telegram_url} target="_blank" rel="noreferrer" className="text-[var(--accent)] hover:underline flex items-center gap-0.5">
                            TG<ExternalLink size={10} />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex gap-1">
                        {lead.status === "pending" && (
                          <Btn size="sm" variant="primary" loading={actionLoading === lead.id + "send"} onClick={() => sendNow(lead.id)}>Send</Btn>
                        )}
                        <Btn size="sm" variant="success" loading={actionLoading === lead.id + "qualified"} onClick={() => patchLead(lead.id, "qualified")}>✓</Btn>
                        <Btn size="sm" variant="danger"  loading={actionLoading === lead.id + "rejected"}  onClick={() => patchLead(lead.id, "rejected")}>✕</Btn>
                        <button
                          onClick={() => handleDeleteLead(lead.id, lead.full_name ?? "this lead")}
                          disabled={actionLoading === lead.id + "del"}
                          title="Delete lead"
                          className="p-1 rounded text-[var(--muted)] hover:text-red-400 hover:bg-red-400/10 transition-colors disabled:opacity-40"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-sm text-[var(--muted)]">
                      No leads match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Slide-out thread panel */}
      {slideLead && (
        <div className="fixed inset-0 z-50 flex">
          <div className="flex-1 bg-black/60 backdrop-blur-sm" onClick={() => setSlideLead(null)} />
          <div className="w-[420px] bg-[var(--panel)] border-l border-[var(--border)] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
              <div>
                <div className="font-semibold">{slideLead.full_name ?? "—"}</div>
                <div className="text-xs text-[var(--muted)]">{slideLead.headline}</div>
                {slideLead.ai_intent && (
                  <span className={`text-xs mt-1 block ${intentColor[slideLead.ai_intent] ?? ""}`}>
                    Intent: {slideLead.ai_intent}
                  </span>
                )}
              </div>
              <button onClick={() => setSlideLead(null)} className="text-[var(--muted)] hover:text-[var(--fg)] text-xl leading-none">×</button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 justify-end">
              {threadLoading && <div className="flex justify-center mt-8"><Spinner /></div>}
              {!threadLoading && thread.length === 0 && (
                <p className="text-sm text-[var(--muted)] text-center mt-8">No messages yet.</p>
              )}
              {thread.map((msg) => (
                <div
                  key={msg.id}
                  className={`max-w-[82%] rounded-xl px-3 py-2 text-sm fade-in ${
                    msg.direction === "sent"
                      ? "ml-auto bg-[var(--accent)]/20 border border-[var(--accent)]/20"
                      : "bg-[var(--panel2)] border border-[var(--border)]"
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words">{msg.text}</div>
                  <div className="text-[10px] text-[var(--muted)] mt-1">
                    {msg.channel} {msg.is_auto && "· AI"} · {new Date(msg.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>

            {/* Inline reply composer */}
            <div className="border-t border-[var(--border)] p-3 grid gap-2">
              <div className="flex gap-1">
                {(["telegram", "linkedin"] as const).map((ch) => (
                  <button
                    key={ch}
                    onClick={() => setSlideChannel(ch)}
                    className={`text-[10px] px-2.5 py-1 rounded font-medium transition-colors capitalize ${
                      slideChannel === ch
                        ? "bg-[var(--accent)] text-white"
                        : "bg-[var(--panel2)] text-[var(--muted)] hover:text-[var(--fg)]"
                    }`}
                  >
                    {ch}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <textarea
                  className="flex-1 bg-[var(--bg2)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs text-[var(--fg)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)] resize-none"
                  rows={2}
                  placeholder={`Reply via ${slideChannel}…`}
                  value={slideReply}
                  onChange={(e) => setSlideReply(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) doSlideReply(); }}
                />
                <button
                  onClick={doSlideReply}
                  disabled={slideSending || !slideReply.trim()}
                  className="self-end px-3 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-medium disabled:opacity-40 hover:bg-[var(--accent)]/80 transition-colors flex items-center gap-1"
                >
                  <Send size={12} />
                  {slideSending ? "…" : "Send"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
