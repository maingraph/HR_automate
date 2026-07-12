"use client";

import { useCallback, useEffect, useState } from "react";
import { getCampaigns, deleteCampaign, updateCampaign, type Campaign } from "@/lib/api";
import Link from "next/link";
import { Badge, Btn, Card, Empty, PageHeader, StatCard } from "@/components/ui";
import { Plus, Trash2, Pause, Play } from "lucide-react";

function statusVariant(s: string): "active" | "draft" | "pending" | "default" {
  if (s === "active") return "active";
  if (s === "draft")  return "draft";
  if (s === "paused") return "pending";
  return "default";
}

export default function OutreachPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading]     = useState(true);
  const [actionId, setActionId]   = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await getCampaigns().catch(() => []);
    setCampaigns(data);
    setLoading(false);
  }, []);

  const handleDelete = useCallback(async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (!confirm(`Delete campaign "${name}" and all its leads? This cannot be undone.`)) return;
    setActionId(id + "del");
    await deleteCampaign(id).catch(() => {});
    setActionId(null);
    load();
  }, [load]);

  const handleTogglePause = useCallback(async (e: React.MouseEvent, campaign: Campaign) => {
    e.stopPropagation();
    const next = campaign.status === "paused" ? "active" : "paused";
    setActionId(campaign.id + "pause");
    await updateCampaign(campaign.id, { status: next }).catch(() => {});
    setActionId(null);
    load();
  }, [load]);

  useEffect(() => {
    load();
    
    // Poll less frequently if no active campaigns
    const hasActiveCampaigns = campaigns.some(c => c.status === 'active');
    const interval = hasActiveCampaigns ? 10000 : 30000;
    
    const iv = setInterval(load, interval);
    return () => clearInterval(iv);
  }, [load, campaigns]);

  const totalLeads   = campaigns.reduce((a, c) => a + (c.total_leads   ?? 0), 0);
  const totalSent    = campaigns.reduce((a, c) => a + (c.sent_count    ?? 0), 0);
  const totalReplied = campaigns.reduce((a, c) => a + (c.replied_count ?? 0), 0);
  const replyRate    = totalSent > 0 ? Math.round((totalReplied / totalSent) * 100) : 0;

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Outreach Campaigns"
        subtitle={`${campaigns.length} campaign${campaigns.length !== 1 ? "s" : ""}`}
        actions={
          <Link href="/outreach/new">
            <Btn variant="primary">
              <Plus size={14} />
              New campaign
            </Btn>
          </Link>
        }
      />

      {/* Stats row */}
      {campaigns.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Total leads"    value={totalLeads}    color="default" />
          <StatCard label="Sent"           value={totalSent}     color="blue"    sub="messages" />
          <StatCard label="Replied"        value={totalReplied}  color="purple"  sub="conversations" />
          <StatCard label="Reply rate"     value={`${replyRate}%`} color={replyRate >= 20 ? "green" : "amber"} />
        </div>
      )}

      {/* Loading shimmer */}
      {loading && (
        <div className="grid gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-xl shimmer" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && campaigns.length === 0 && (
        <Card className="p-0">
          <Empty
            icon="📢"
            title="No campaigns yet"
            subtitle="Create your first outreach campaign to start contacting candidates."
          />
          <div className="pb-6 flex justify-center">
            <Link href="/outreach/new">
              <Btn variant="primary"><Plus size={14} /> New campaign</Btn>
            </Link>
          </div>
        </Card>
      )}

      {/* Campaign table */}
      {!loading && campaigns.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--panel2)]">
                  {["Campaign", "Mode", "Leads", "Sent", "Replied", "Status", "Actions"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => (window.location.href = `/outreach/${c.id}`)}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--panel2)] cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-[var(--fg)]">{c.name}</div>
                      {c.job_id && (
                        <div className="text-xs text-[var(--muted)] mt-0.5 truncate max-w-[180px]">
                          Job #{c.job_id.slice(0, 8)}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={(c.outreach_mode as "copilot" | "autopilot") ?? "copilot"}>
                        {c.outreach_mode === "autopilot" ? "🤖 Autopilot" : "👁 Copilot"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-[var(--fg2)]">{c.total_leads ?? 0}</td>
                    <td className="px-4 py-3 font-mono text-blue-400">{c.sent_count ?? 0}</td>
                    <td className="px-4 py-3 font-mono text-purple-400">{c.replied_count ?? 0}</td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                        <Link
                          href={`/outreach/${c.id}`}
                          className="text-xs text-[var(--accent)] hover:underline"
                        >
                          View →
                        </Link>
                        {(c.status === "active" || c.status === "paused") && (
                          <button
                            onClick={(e) => handleTogglePause(e, c)}
                            disabled={actionId === c.id + "pause"}
                            title={c.status === "paused" ? "Resume campaign" : "Pause campaign"}
                            className="p-1.5 rounded-lg text-[var(--muted)] hover:text-amber-400 hover:bg-amber-400/10 transition-colors disabled:opacity-40"
                          >
                            {c.status === "paused" ? <Play size={13} /> : <Pause size={13} />}
                          </button>
                        )}
                        <button
                          onClick={(e) => handleDelete(e, c.id, c.name)}
                          disabled={actionId === c.id + "del"}
                          title="Delete campaign"
                          className="p-1.5 rounded-lg text-[var(--muted)] hover:text-red-400 hover:bg-red-400/10 transition-colors disabled:opacity-40"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
