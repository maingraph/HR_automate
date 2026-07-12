"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getInbox, getThread, sendReply, type Lead, type Message } from "@/lib/api";
import { Badge, Btn, Empty, Spinner } from "@/components/ui";
import { intentLabel } from "@/lib/intent";
import { Send, Bot } from "lucide-react";

type Filter = "all" | "unread" | "needs_review" | "qualified";

const channelOptions = [
  { value: "telegram", label: "Telegram" },
  { value: "linkedin", label: "LinkedIn" },
];

export default function InboxPage() {
  const [leads, setLeads]           = useState<Lead[]>([]);
  const [selected, setSelected]     = useState<Lead | null>(null);
  const [thread, setThread]         = useState<Message[]>([]);
  const [threadLoading, setThreadLoading] = useState(false);
  const [replyText, setReplyText]   = useState("");
  const [channel, setChannel]       = useState<"telegram" | "linkedin">("telegram");
  const [sending, setSending]       = useState(false);
  const [filter, setFilter]         = useState<Filter>("all");

  const loadLeads = useCallback(async () => {
    const data = await getInbox().catch(() => []);
    setLeads(data);
  }, []);

  const loadThread = useCallback(async (leadId: string) => {
    setThreadLoading(true);
    const msgs = await getThread(leadId).catch(() => []);
    setThread(msgs);
    setThreadLoading(false);
  }, []);

  useEffect(() => {
    loadLeads();
    // Longer interval when no conversation selected (30s), shorter when selected (10s)
    const interval = selected ? 10000 : 30000;
    const iv = setInterval(loadLeads, interval);
    return () => clearInterval(iv);
  }, [loadLeads, selected]);

  useEffect(() => {
    if (!selected) return;
    loadThread(selected.id);
    // Poll thread every 10s when conversation is open
    const iv = setInterval(() => loadThread(selected.id), 10000);
    return () => clearInterval(iv);
  }, [selected?.id, loadThread]);

  const doSend = useCallback(async () => {
    if (!selected || !replyText.trim()) return;
    setSending(true);
    await sendReply(selected.id, replyText.trim(), channel).catch(() => {});
    setReplyText("");
    setSending(false);
    loadThread(selected.id);
    loadLeads();
  }, [selected, replyText, channel, loadThread, loadLeads]);

  const filtered = useMemo(() => {
    return leads.filter((l) => {
      if (filter === "unread")       return (l.unread_count ?? 0) > 0;
      if (filter === "needs_review") return l.needs_review;
      if (filter === "qualified")    return l.status === "qualified";
      return true;
    });
  }, [leads, filter]);

  const unreadCount      = leads.reduce((a, l) => a + (l.unread_count ?? 0), 0);
  const needsReviewCount = leads.filter((l) => l.needs_review).length;

  const FILTERS: { key: Filter; label: string; count?: number }[] = [
    { key: "all",          label: "All",          count: leads.length },
    { key: "unread",       label: "Unread",       count: unreadCount },
    { key: "needs_review", label: "Needs Review", count: needsReviewCount },
    { key: "qualified",    label: "Qualified" },
  ];

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Inbox</h1>
          <p className="text-sm text-[var(--muted)]">Unified candidate conversation view</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-1.5 flex-wrap">
        {FILTERS.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === key
                ? "bg-[var(--accent)] text-white"
                : "bg-[var(--panel)] border border-[var(--border)] text-[var(--muted)] hover:text-[var(--fg)]"
            }`}
          >
            {label}
            {count !== undefined && count > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                filter === key ? "bg-white/20 text-white" :
                key === "needs_review" ? "bg-amber-500 text-white" :
                "bg-[var(--border2)] text-[var(--fg2)]"
              }`}>
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Main split pane */}
      <div
        className="flex border border-[var(--border)] rounded-xl overflow-hidden bg-[var(--panel)]"
        style={{ height: "calc(100vh - 280px)", minHeight: 500 }}
      >
        {/* Lead list */}
        <div className="w-72 border-r border-[var(--border)] overflow-y-auto flex-shrink-0">
          {filtered.length === 0 && (
            <Empty icon="💬" title="No conversations" subtitle="Matching leads will appear here" />
          )}
          {filtered.map((lead) => {
            const intent = lead.ai_intent ? intentLabel[lead.ai_intent] : null;
            return (
              <button
                key={lead.id}
                onClick={() => { setSelected(lead); setReplyText(""); }}
                className={`w-full text-left px-4 py-3 border-b border-[var(--border)] transition-colors hover:bg-[var(--panel2)] ${
                  selected?.id === lead.id
                    ? "bg-[var(--panel2)] border-l-2 border-l-[var(--accent)]"
                    : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm truncate text-[var(--fg)]">
                    {lead.full_name ?? "Unknown"}
                  </span>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {lead.needs_review && (
                      <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" title="AI draft pending review" />
                    )}
                    {(lead.unread_count ?? 0) > 0 && (
                      <span className="bg-[var(--accent)] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                        {lead.unread_count}
                      </span>
                    )}
                  </div>
                </div>
                {lead.headline && (
                  <div className="text-xs text-[var(--muted)] truncate mt-0.5">{lead.headline}</div>
                )}
                <div className="flex items-center gap-2 mt-1">
                  {intent && <Badge variant={intent.variant} className="text-[9px]">{intent.label}</Badge>}
                  {lead.last_message && (
                    <span className="text-xs text-[var(--muted)] truncate">{lead.last_message}</span>
                  )}
                </div>
                {lead.last_message_at && (
                  <div className="text-[10px] text-[var(--muted)] mt-1">
                    {new Date(lead.last_message_at).toLocaleString()}
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Thread pane */}
        <div className="flex-1 flex flex-col min-w-0">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-sm text-[var(--muted)]">
              Select a conversation to view messages
            </div>
          ) : (
            <>
              {/* Conversation header */}
              <div className="px-4 py-3 border-b border-[var(--border)] bg-[var(--panel2)] flex items-center justify-between">
                <div>
                  <div className="font-semibold text-[var(--fg)]">{selected.full_name ?? "—"}</div>
                  <div className="text-xs text-[var(--muted)]">{selected.headline}</div>
                </div>
                <div className="flex items-center gap-2">
                  {selected.ai_intent && (
                    <Badge variant={intentLabel[selected.ai_intent]?.variant ?? "other"}>
                      {intentLabel[selected.ai_intent]?.label ?? selected.ai_intent}
                    </Badge>
                  )}
                  <Badge variant={selected.status as "pending" | "sent" | "replied" | "qualified" | "rejected" | "default"}>
                    {selected.status}
                  </Badge>
                </div>
              </div>

              {/* AI draft banner */}
              {selected.needs_review && selected.ai_draft && (
                <div className="mx-4 mt-3 bg-amber-900/20 border border-amber-800/40 rounded-xl p-3 text-sm">
                  <div className="flex items-center gap-2 text-amber-400 font-medium mb-2 text-xs">
                    <Bot size={13} />
                    AI Draft — awaiting your approval
                  </div>
                  <div className="text-[var(--fg2)] whitespace-pre-wrap text-xs leading-relaxed mb-3">
                    {selected.ai_draft}
                  </div>
                  <div className="flex gap-2">
                    <Btn
                      variant="success"
                      size="sm"
                      onClick={async () => {
                        const { approveDraft } = await import("@/lib/api");
                        await approveDraft(selected.id, selected.ai_draft, selected.preferred_channel ?? "telegram").catch(() => {});
                        loadLeads();
                        loadThread(selected.id);
                        setSelected((s) => s ? { ...s, needs_review: false, ai_draft: undefined } : s);
                      }}
                    >
                      ✓ Send draft
                    </Btn>
                    <Btn
                      variant="ghost"
                      size="sm"
                      onClick={() => setReplyText(selected.ai_draft!)}
                    >
                      ✏️ Edit before sending
                    </Btn>
                    <Btn
                      variant="danger"
                      size="sm"
                      onClick={async () => {
                        const { rejectDraft } = await import("@/lib/api");
                        await rejectDraft(selected.id).catch(() => {});
                        setSelected((s) => s ? { ...s, needs_review: false, ai_draft: undefined } : s);
                        loadLeads();
                      }}
                    >
                      Discard
                    </Btn>
                  </div>
                </div>
              )}

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 justify-end">
                {threadLoading && (
                  <div className="flex justify-center"><Spinner size="md" /></div>
                )}
                {!threadLoading && thread.length === 0 && (
                  <p className="text-sm text-[var(--muted)] text-center">No messages yet.</p>
                )}
                {thread.map((msg) => (
                  <div
                    key={msg.id}
                    className={`max-w-[78%] rounded-xl px-3.5 py-2.5 text-sm fade-in ${
                      msg.direction === "sent"
                        ? "ml-auto bg-[var(--accent)]/20 border border-[var(--accent)]/20"
                        : "bg-[var(--panel2)] border border-[var(--border)]"
                    }`}
                  >
                    <div className="whitespace-pre-wrap break-words text-[var(--fg)]">{msg.text}</div>
                    <div className="text-[10px] text-[var(--muted)] mt-1.5 flex items-center gap-2">
                      <span>{msg.channel}</span>
                      {msg.is_auto && <span className="text-[var(--accent)]">· AI</span>}
                      <span>· {new Date(msg.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Reply composer */}
              <div className="border-t border-[var(--border)] p-3 grid gap-2">
                <div className="flex gap-1">
                  {channelOptions.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setChannel(opt.value as "telegram" | "linkedin")}
                      className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                        channel === opt.value
                          ? "bg-[var(--accent)] text-white"
                          : "bg-[var(--panel2)] text-[var(--muted)] hover:text-[var(--fg)]"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <textarea
                    className="flex-1 bg-[var(--bg2)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)] resize-none"
                    rows={2}
                    placeholder={`Reply via ${channel}…`}
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) doSend();
                    }}
                  />
                  <Btn
                    variant="primary"
                    disabled={sending || !replyText.trim()}
                    loading={sending}
                    onClick={doSend}
                    className="self-end"
                  >
                    <Send size={14} />
                    {sending ? "" : "Send"}
                  </Btn>
                </div>
                <p className="text-[10px] text-[var(--muted)]">Ctrl+Enter to send</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
