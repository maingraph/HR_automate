"use client";

import { useCallback, useEffect, useState } from "react";
import { getCampaigns, getNeedsReview, approveDraft, rejectDraft, type Campaign, type Lead } from "@/lib/api";
import { Badge, Btn, Card, Empty, PageHeader, Spinner } from "@/components/ui";
import { intentVariant } from "@/lib/intent";
import { Bot, Check, X, Edit3, RefreshCw } from "lucide-react";

type ReviewItem = Lead & { _campaign?: Campaign };

export default function ReviewQueuePage() {
  const [items, setItems]           = useState<ReviewItem[]>([]);
  const [loading, setLoading]       = useState(true);
  const [editId, setEditId]         = useState<string | null>(null);
  const [editText, setEditText]     = useState("");
  const [processing, setProcessing] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const campaigns = await getCampaigns();
      const allItems: ReviewItem[] = [];
      await Promise.all(
        campaigns.map(async (c) => {
          const leads = await getNeedsReview(c.id).catch(() => []);
          leads.forEach((l) => allItems.push({ ...l, _campaign: c }));
        })
      );
      // Sort newest first
      allItems.sort((a, b) => new Date(b.last_message_at ?? 0).getTime() - new Date(a.last_message_at ?? 0).getTime());
      setItems(allItems);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    
    // Poll less frequently if queue is empty
    const interval = items.length > 0 ? 15000 : 60000;
    
    const iv = setInterval(load, interval);
    return () => clearInterval(iv);
  }, [load, items.length]);

  const doApprove = async (item: ReviewItem, textOverride?: string) => {
    setProcessing((p) => ({ ...p, [item.id]: true }));
    await approveDraft(item.id, textOverride ?? item.ai_draft, item.preferred_channel ?? "telegram").catch(() => {});
    setItems((prev) => prev.filter((i) => i.id !== item.id));
    setProcessing((p) => ({ ...p, [item.id]: false }));
    setEditId(null);
  };

  const doReject = async (item: ReviewItem) => {
    setProcessing((p) => ({ ...p, [item.id]: true }));
    await rejectDraft(item.id).catch(() => {});
    setItems((prev) => prev.filter((i) => i.id !== item.id));
    setProcessing((p) => ({ ...p, [item.id]: false }));
  };

  const isProcessing = (id: string) => !!processing[id];

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Review Queue"
        subtitle="AI-drafted replies awaiting your approval (Copilot mode)"
        actions={
          <Btn variant="ghost" onClick={load} loading={loading}>
            <RefreshCw size={14} />
            Refresh
          </Btn>
        }
      />

      {/* Info banner */}
      <div className="bg-[var(--panel)] border border-[var(--border2)] rounded-xl px-4 py-3 text-sm text-[var(--fg2)] flex items-center gap-3">
        <Bot size={18} className="text-[var(--accent)] flex-shrink-0" />
        <span>
          The AI classified each reply and drafted a context-aware response. Review, edit if needed, then approve to send.
          Switch a campaign to <strong className="text-purple-400">Autopilot</strong> in its settings to skip this step.
        </span>
      </div>

      {loading && (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      )}

      {!loading && items.length === 0 && (
        <Card>
          <Empty
            icon="✅"
            title="Review queue is empty"
            subtitle="All AI drafts have been reviewed. New replies will appear here when the agent receives messages."
          />
        </Card>
      )}

      {!loading && items.length > 0 && (
        <div className="grid gap-3">
          {items.map((item) => (
            <Card key={item.id} className="p-4 grid gap-3">
              {/* Lead header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full bg-[var(--panel2)] border border-[var(--border)] flex items-center justify-center text-sm font-semibold text-[var(--fg2)] flex-shrink-0">
                    {(item.full_name ?? "?")[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="font-semibold text-[var(--fg)]">{item.full_name ?? "Unknown lead"}</div>
                    {item.headline && <div className="text-xs text-[var(--muted)] mt-0.5">{item.headline}</div>}
                    <div className="flex items-center gap-2 mt-1">
                      {item._campaign && (
                        <span className="text-xs text-[var(--muted)]">{item._campaign.name}</span>
                      )}
                      <span className="text-[var(--border2)]">·</span>
                      {item.preferred_channel && (
                        <span className="text-xs text-[var(--muted)] capitalize">{item.preferred_channel}</span>
                      )}
                    </div>
                  </div>
                </div>
                <Badge variant={intentVariant(item.ai_intent) as "interested" | "questions" | "declined" | "other"}>
                  {item.ai_intent ?? "other"}
                </Badge>
              </div>

              {/* Candidate's last message */}
              {item.last_message && (
                <div className="bg-[var(--panel2)] border border-[var(--border)] rounded-lg px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-1">Their message</p>
                  <p className="text-sm text-[var(--fg2)]">{item.last_message}</p>
                  {item.last_message_at && (
                    <p className="text-[10px] text-[var(--muted)] mt-1">
                      {new Date(item.last_message_at).toLocaleString()}
                    </p>
                  )}
                </div>
              )}

              {/* AI Draft */}
              <div className="bg-amber-950/30 border border-amber-800/40 rounded-lg px-3 py-2">
                <div className="flex items-center gap-1.5 text-amber-400 text-[10px] uppercase tracking-wider mb-2">
                  <Bot size={11} />
                  AI Draft
                </div>

                {editId === item.id ? (
                  <textarea
                    className="w-full bg-[var(--bg2)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--fg)] focus:outline-none focus:border-[var(--accent)] resize-y min-h-[80px]"
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                  />
                ) : (
                  <p className="text-sm text-[var(--fg2)] whitespace-pre-wrap leading-relaxed">
                    {item.ai_draft ?? "—"}
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-wrap">
                {editId === item.id ? (
                  <>
                    <Btn
                      variant="success"
                      size="sm"
                      loading={isProcessing(item.id)}
                      onClick={() => doApprove(item, editText)}
                    >
                      <Check size={13} />
                      Send edited draft
                    </Btn>
                    <Btn variant="ghost" size="sm" onClick={() => setEditId(null)}>
                      Cancel
                    </Btn>
                  </>
                ) : (
                  <>
                    <Btn
                      variant="success"
                      size="sm"
                      loading={isProcessing(item.id)}
                      onClick={() => doApprove(item)}
                    >
                      <Check size={13} />
                      Approve & send
                    </Btn>
                    <Btn
                      variant="secondary"
                      size="sm"
                      disabled={isProcessing(item.id)}
                      onClick={() => {
                        setEditId(item.id);
                        setEditText(item.ai_draft ?? "");
                      }}
                    >
                      <Edit3 size={13} />
                      Edit
                    </Btn>
                    <Btn
                      variant="danger"
                      size="sm"
                      loading={isProcessing(item.id)}
                      onClick={() => doReject(item)}
                    >
                      <X size={13} />
                      Discard
                    </Btn>
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
