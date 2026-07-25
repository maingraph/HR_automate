"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

type Job = {
  id: string;
  title: string;
  status: string;
  created_at: string;
  stats?: { telegram_count?: number; apollo_count?: number; linkedin_count?: number };
};

type DashboardStats = {
  total_jobs: number;
  active_jobs: number;
  total_candidates: number;
  recent_jobs: Job[];
};

const statusColors: Record<string, string> = {
  queued: "text-[var(--muted)]",
  running: "text-[var(--accent)]",
  running_deep: "text-[var(--accent)]",
  paused: "text-yellow-500",
  phase1_done: "text-blue-400",
  done: "text-[var(--green)]",
  error: "text-red-400",
};

const statusLabels: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  running_deep: "Deep Scan",
  paused: "Paused",
  phase1_done: "Phase 1 Done",
  done: "Complete",
  error: "Error",
};

function StatCard({ icon, label, value, accent }: { icon: string; label: string; value: number; accent: string }) {
  return (
    <div className="card group hover-ambient">
      <div className={`w-10 h-10 rounded-full bg-[var(--panel2)] flex items-center justify-center ${accent}`}>
        <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
          {icon}
        </span>
      </div>
      <div className="mt-4">
        <p className="font-body text-body-sm text-[var(--muted)] mb-1">{label}</p>
        <h2 className="font-display text-[36px] font-bold text-[var(--fg)] leading-none">{value}</h2>
      </div>
    </div>
  );
}

function QuickStart() {
  const router = useRouter();
  const [role, setRole] = useState("");
  const [skills, setSkills] = useState("");

  function launch() {
    // Hand off to the full job wizard, prefilled. Avoids duplicating the
    // Gemini-plan job-creation flow that /jobs/new already owns.
    try {
      sessionStorage.setItem(
        "quickstart",
        JSON.stringify({ title: role.trim(), skills: skills.trim() })
      );
    } catch {
      /* sessionStorage unavailable — wizard just opens blank */
    }
    router.push("/jobs/new");
  }

  return (
    <div className="card">
      <h3 className="font-title text-title-sm text-[var(--fg)] flex items-center gap-2 mb-1">
        <span className="material-symbols-outlined text-[var(--accent)]">rocket_launch</span>
        Quick Start Sourcing
      </h3>
      <p className="font-body text-body-sm text-[var(--muted)] mb-md">
        Kick off a targeted AI search. We&apos;ll open the wizard prefilled.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-body-sm text-[var(--muted)] mb-1.5">Target Role</label>
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Senior Frontend Engineer"
            className="input w-full"
            onKeyDown={(e) => e.key === "Enter" && role.trim() && launch()}
          />
        </div>
        <div>
          <label className="block text-body-sm text-[var(--muted)] mb-1.5">Mandatory Skills</label>
          <input
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            placeholder="React, TypeScript, …"
            className="input w-full"
            onKeyDown={(e) => e.key === "Enter" && role.trim() && launch()}
          />
        </div>
        <div className="flex justify-end">
          <button onClick={launch} disabled={!role.trim()} className="btn-primary flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px]">bolt</span>
            Launch Sourcing Agent
          </button>
        </div>
      </div>
    </div>
  );
}

function DashboardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = (searchParams.get("q") || "").toLowerCase();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const jobsRes = await apiFetch<Job[]>("/jobs");
        const activeJobs = jobsRes.filter((j) =>
          ["queued", "running", "running_deep"].includes(j.status)
        );
        const datasetCounts = await Promise.all(
          jobsRes.map(async (job) => {
            try {
              const datasets = await apiFetch<Array<{ row_count?: number }>>(`/jobs/${job.id}/datasets`);
              return Math.max(0, ...datasets.map((dataset) => dataset.row_count || 0));
            } catch {
              return (
                (job.stats?.telegram_count || 0) +
                (job.stats?.apollo_count || 0) +
                (job.stats?.linkedin_count || 0)
              );
            }
          })
        );
        const totalCandidates = datasetCounts.reduce((sum, count) => sum + count, 0);
        setStats({
          total_jobs: jobsRes.length,
          active_jobs: activeJobs.length,
          total_candidates: totalCandidates,
          recent_jobs: jobsRes.slice(0, 12),
        });
      } catch (err) {
        console.error("Failed to load stats:", err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const visibleJobs = useMemo(() => {
    const jobs = stats?.recent_jobs || [];
    if (!q) return jobs;
    return jobs.filter((j) => j.title.toLowerCase().includes(q));
  }, [stats, q]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-[var(--muted)]">Loading…</div>
      </div>
    );
  }

  return (
    <div className="space-y-lg">
      {/* Page Header */}
      <div>
        <h1 className="font-headline text-headline-md text-[var(--fg)]">Overview</h1>
        <p className="font-body text-body-md text-[var(--muted)] mt-1">
          Here is a summary of your active sourcing pipeline.
        </p>
      </div>

      {/* Stat cards (real data only) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-md">
        <StatCard icon="work" label="Total Jobs" value={stats?.total_jobs || 0} accent="text-[var(--accent)]" />
        <StatCard icon="pending_actions" label="Active Jobs" value={stats?.active_jobs || 0} accent="text-[var(--accent)]" />
        <StatCard icon="group" label="Candidates Sourced" value={stats?.total_candidates || 0} accent="text-[var(--green)]" />
      </div>

      {/* Two-panel: Quick Start + Recent Jobs */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-md">
        <div className="lg:col-span-3">
          <QuickStart />
        </div>

        <div className="lg:col-span-2">
          <div className="card h-full">
            <div className="flex items-center justify-between mb-md">
              <h3 className="font-title text-title-sm text-[var(--fg)] flex items-center gap-2">
                <span className="material-symbols-outlined text-[var(--accent)]">list</span>
                Recent Jobs
              </h3>
              {q && (
                <span className="text-xs text-[var(--muted)]">
                  filtered: “{searchParams.get("q")}”
                </span>
              )}
            </div>

            {visibleJobs.length > 0 ? (
              <div className="space-y-2">
                {visibleJobs.map((job) => (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="block p-3 rounded-lg border border-[var(--border)] hover:border-[var(--accent)]/30 hover:bg-[var(--panel2)] transition-all"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-body text-body-md text-[var(--fg)] font-medium truncate">
                          {job.title}
                        </h4>
                        <p className="font-body text-body-sm text-[var(--muted)] mt-0.5">
                          {new Date(job.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <span className={`font-label text-label-sm shrink-0 ${statusColors[job.status] || "text-[var(--muted)]"}`}>
                        {statusLabels[job.status] || job.status}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <span className="material-symbols-outlined text-[48px] text-[var(--muted)] mb-4 block">
                  {q ? "search_off" : "inbox"}
                </span>
                <p className="font-body text-body-md text-[var(--muted)] mb-4">
                  {q ? "No jobs match your search." : "No jobs yet. Create your first sourcing job."}
                </p>
                {!q && (
                  <button onClick={() => router.push("/jobs/new")} className="btn-primary">
                    Create Job
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return (
    <Suspense fallback={<div className="min-h-[400px]" />}>
      <DashboardInner />
    </Suspense>
  );
}
