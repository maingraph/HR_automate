"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, API } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Btn, Field, inputCls, Spinner } from "@/components/ui";
import { useForm } from "@/lib/hooks/useForm";
import { Upload, Zap, Search, MessageSquare, Database, Briefcase } from "lucide-react";

type JobCreatePayload = {
  title: string;
  description?: string;
  skills: string[];
  geo?: string;
  geo_exclude: string[];
  seniority?: string;
  budget_min?: number;
  budget_max?: number;
  tg_channels: string[];
  sources: string[];
};

const ALL_SOURCES = [
  { id: "linkedin",          label: "LinkedIn (Apify)",    icon: Briefcase,     desc: "Boolean search via Apify actor" },
  { id: "linkedin_salesnav", label: "LinkedIn Sales Nav",  icon: Briefcase,     desc: "Playwright scrape — needs li_at cookie" },
  { id: "telegram",          label: "Telegram",            icon: MessageSquare, desc: "Channel keyword scrape" },
  { id: "xlsx",              label: "XLSX / CSV",          icon: Database,      desc: "SalesNav export or any lead list" },
  { id: "apollo",            label: "Apollo.io",           icon: Search,        desc: "Requires APOLLO_API_KEY" },
] as const;

// Wizard steps
const STEPS = ["Vacancy", "Sources", "Launch"] as const;

export default function NewJobPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [xlsxFile, setXlsxFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [discoveredChannels, setDiscoveredChannels] = useState<Array<{handle: string; reason: string; confidence: string}>>([]);
  const [discoveringChannels, setDiscoveringChannels] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // AI Vacancy Structuring state
  const [showStructureDialog, setShowStructureDialog] = useState(false);
  const [rawVacancyText, setRawVacancyText] = useState("");
  const [structuring, setStructuring] = useState(false);

  const { values, setValue, isSubmitting, handleSubmit } = useForm({
    initialValues: {
      title: "",
      description: "",
      skills: "",
      geo: "",
      geo_exclude: "",
      seniority: "",
      budget_min: "" as string | number,
      budget_max: "" as string | number,
      tg_channels: "",
      sources: ["telegram"] as string[],
    },
    validations: [
      {
        field: "title",
        validate: (v) => !v.trim() ? "Vacancy title is required" : null,
      },
    ],
    onSubmit: async (formValues) => {
      if (formValues.sources.includes("xlsx") && !xlsxFile) {
        setError("Please upload an XLSX/CSV file");
        throw new Error("Please upload an XLSX/CSV file");
      }
      
      // Warn if Telegram selected but no channels (not blocking)
      if (formValues.sources.includes("telegram") && !formValues.tg_channels.trim()) {
        const proceed = confirm(
          "⚠️ No Telegram channels specified.\n\n" +
          "Telegram scraping will be skipped. Continue with other sources?\n\n" +
          "Tip: Add channels like @python_jobs, @remotejobs for better results."
        );
        if (!proceed) {
          throw new Error("Cancelled by user");
        }
      }

      setError(null);
      const geo_exclude = formValues.geo_exclude.split(",").map((s) => s.trim()).filter(Boolean);
      const payload: JobCreatePayload = {
        title: formValues.title.trim(),
        description: formValues.description.trim() || undefined,
        skills: formValues.skills.split(",").map((s) => s.trim()).filter(Boolean),
        geo: formValues.geo || undefined,
        geo_exclude,
        seniority: formValues.seniority || undefined,
        budget_min: formValues.budget_min ? +formValues.budget_min : undefined,
        budget_max: formValues.budget_max ? +formValues.budget_max : undefined,
        tg_channels: formValues.tg_channels.split(",").map((s) => s.trim()).filter(Boolean),
        sources: formValues.sources,
      };

      const job = await apiFetch<{ id: string }>("/jobs", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (xlsxFile) {
        const fd = new FormData();
        fd.append("file", xlsxFile);
        const res = await fetch(`${API}/jobs/${job.id}/ingest-file`, { method: "POST", body: fd });
        if (!res.ok) throw new Error(`File upload failed: ${await res.text()}`);
        router.push(`/jobs/${job.id}`);
        return;
      }

      await apiFetch(`/jobs/${job.id}/run`, { method: "POST" });
      router.push(`/jobs/${job.id}`);
    },
  });

  // Prefill from the dashboard Quick Start handoff (sessionStorage), consumed once.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("quickstart");
      if (!raw) return;
      sessionStorage.removeItem("quickstart");
      const { title, skills } = JSON.parse(raw) as { title?: string; skills?: string };
      if (title) setValue("title", title);
      if (skills) setValue("skills", skills);
    } catch {
      /* ignore malformed handoff */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleSource = (id: string) => {
    setValue("sources", values.sources.includes(id)
      ? values.sources.filter((s) => s !== id)
      : [...values.sources, id]
    );
  };

  const xlsxSelected = values.sources.includes("xlsx");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setXlsxFile(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setXlsxFile(f);
  };

  const handleDiscoverChannels = async () => {
    if (!values.title.trim()) {
      alert("Please enter a job title first");
      return;
    }

    setDiscoveringChannels(true);
    setError(null);

    try {
      // Create a temporary job object for discovery
      const tempJob = {
        title: values.title,
        description: values.description,
        skills: values.skills.split(",").map(s => s.trim()).filter(Boolean),
        geo: values.geo,
        seniority: values.seniority,
      };

      // Call discovery API (we'll use a direct endpoint that doesn't require job_id)
      const response = await apiFetch<{
        channels?: Array<{ handle: string; reason: string; confidence: string }>;
      }>("/jobs/discover-channels-preview", {
        method: "POST",
        body: JSON.stringify(tempJob),
      });

      const channels = response.channels || [];
      setDiscoveredChannels(channels);

      if (channels.length === 0) {
        alert("No channels found. Try adding more details to your job description.");
      }
    } catch (err) {
      console.error("Channel discovery failed:", err);
      setError("Failed to discover channels. Please try again.");
    } finally {
      setDiscoveringChannels(false);
    }
  };

  const addChannel = (handle: string) => {
    const current = values.tg_channels.trim();
    const channels = current ? current.split(",").map(s => s.trim()) : [];
    
    if (!channels.includes(handle)) {
      channels.push(handle);
      setValue("tg_channels", channels.join(", "));
    }
  };

  const handleStructureVacancy = async () => {
    if (!rawVacancyText.trim()) {
      alert("Please paste some vacancy text first");
      return;
    }

    setStructuring(true);
    setError(null);

    try {
      const result = await apiFetch<{
        title?: string;
        description?: string;
        skills?: string[];
        seniority?: string;
        geo?: string;
        budget_min?: string | number;
        budget_max?: string | number;
      }>("/jobs/structure-vacancy", {
        method: "POST",
        body: JSON.stringify({ raw_text: rawVacancyText })
      });

      // Populate form fields with extracted data
      setValue("title", result.title || "");
      setValue("description", result.description || "");
      setValue("skills", (result.skills || []).join(", "));
      setValue("seniority", result.seniority || "");
      setValue("geo", result.geo || "");
      setValue("budget_min", result.budget_min || "");
      setValue("budget_max", result.budget_max || "");

      // Close dialog and show success
      setShowStructureDialog(false);
      setRawVacancyText("");
      
      // Optional: Show a brief success message
      setTimeout(() => {
        // You could add a toast notification here
      }, 100);
    } catch (err: any) {
      console.error("Vacancy structuring failed:", err);
      setError(err.message || "Failed to structure vacancy. Please try again.");
    } finally {
      setStructuring(false);
    }
  };

  return (
    <div className="container-max">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-lg">
          <h1 className="font-headline text-headline-md text-[var(--fg)]">Create Sourcing Job</h1>
          <p className="font-body text-body-md text-[var(--muted)] mt-1">
            AI-powered candidate sourcing across multiple channels
          </p>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center gap-2 mb-lg">
          {STEPS.map((label, i) => (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div className={`flex items-center gap-2 flex-1 px-4 py-2 rounded-lg border transition-colors ${
                i === step 
                  ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]" 
                  : i < step 
                  ? "border-[var(--green)] bg-[var(--green)]/10 text-[var(--green)]"
                  : "border-[var(--border)] text-[var(--muted)]"
              }`}>
                <span className="font-label text-label-sm font-semibold">{i + 1}</span>
                <span className="font-body text-body-sm">{label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <span className="material-symbols-outlined text-[var(--muted)]">chevron_right</span>
              )}
            </div>
          ))}
        </div>

        {error && (
          <div className="mb-md p-4 bg-red-900/10 border border-red-600 rounded-lg">
            <p className="font-body text-body-sm text-red-400">{error}</p>
          </div>
        )}

        <div className="card">
          {/* Step 1: Vacancy Details */}
          {step === 0 && (
            <div className="grid gap-6">
              {/* AI Structure Button */}
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-[var(--muted)]">
                  Fill out the form manually, or use AI to extract from raw text
                </div>
                <button
                  type="button"
                  onClick={() => setShowStructureDialog(true)}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] text-[var(--fg2)] hover:bg-[var(--panel2)] transition-colors"
                >
                  <Zap size={14} />
                  Structure with AI
                </button>
              </div>

              <Field label="Vacancy title" required>
                <input
                  className={inputCls}
                  placeholder="Senior Frontend Engineer"
                  value={values.title}
                  onChange={(e) => setValue("title", e.target.value)}
                  autoFocus
                />
              </Field>

              <Field label="Description" hint="Optional — helps AI generate better search queries">
                <textarea
                  className={inputCls}
                  rows={4}
                  placeholder="We're looking for an experienced React developer..."
                  value={values.description}
                  onChange={(e) => setValue("description", e.target.value)}
                />
              </Field>

              <Field label="Required skills (comma-separated)" hint="e.g. React, TypeScript, Node.js">
                <input
                  className={inputCls}
                  placeholder="React, TypeScript, Node.js"
                  value={values.skills}
                  onChange={(e) => setValue("skills", e.target.value)}
                />
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Target geo">
                  <input
                    className={inputCls}
                    placeholder="Remote / CIS / Ukraine"
                    value={values.geo}
                    onChange={(e) => setValue("geo", e.target.value)}
                  />
                </Field>
                <Field label="Seniority">
                  <input
                    className={inputCls}
                    placeholder="Mid-Senior"
                    value={values.seniority}
                    onChange={(e) => setValue("seniority", e.target.value)}
                  />
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Budget min ($)" hint="Monthly spend or salary floor">
                  <input
                    type="number"
                    className={inputCls}
                    placeholder="70000"
                    value={values.budget_min}
                    onChange={(e) => setValue("budget_min", e.target.value)}
                  />
                </Field>
                <Field label="Budget max ($)">
                  <input
                    type="number"
                    className={inputCls}
                    placeholder="100000"
                    value={values.budget_max}
                    onChange={(e) => setValue("budget_max", e.target.value)}
                  />
                </Field>
              </div>

              <Field label="Excluded geos (comma-separated)" hint="Candidates matching these terms will be rejected">
                <input
                  className={inputCls + " border-amber-800/40 focus:border-amber-500"}
                  placeholder="ukraine, +380, Kyiv — leave blank to disable"
                  value={values.geo_exclude}
                  onChange={(e) => setValue("geo_exclude", e.target.value)}
                />
              </Field>

              <Btn
                variant="primary"
                size="lg"
                className="w-full justify-center mt-2"
                onClick={() => {
                  if (!values.title.trim()) { setError("Vacancy title is required"); return; }
                  setError(null);
                  setStep(1);
                }}
              >
                Continue to Sources →
              </Btn>
            </div>
          )}

          {/* Step 2: Sources */}
          {step === 1 && (
            <div className="grid gap-6">
              <div>
                <p className="text-sm font-medium text-[var(--fg2)] mb-3">Choose sourcing channels</p>
                <div className="grid grid-cols-2 gap-2">
                  {ALL_SOURCES.map(({ id, label, icon: Icon, desc }) => {
                    const active = values.sources.includes(id);
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => toggleSource(id)}
                        className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-left transition-all ${
                          active
                            ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--fg)] shadow-lg"
                            : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)]/40 hover:bg-[var(--panel2)]"
                        }`}
                      >
                        <Icon size={18} className={`mt-0.5 flex-shrink-0 ${active ? "text-[var(--accent)]" : ""}`} />
                        <div>
                          <div className={`text-sm font-medium ${active ? "text-[var(--fg)]" : ""}`}>{label}</div>
                          <div className="text-[11px] opacity-60 mt-0.5">{desc}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {values.sources.includes("telegram") && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                      Telegram channels (optional)
                    </label>
                    <button
                      type="button"
                      onClick={handleDiscoverChannels}
                      disabled={discoveringChannels || !values.title.trim()}
                      className="text-xs text-[var(--accent)] hover:text-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                    >
                      {discoveringChannels ? (
                        <>
                          <span className="animate-spin">⏳</span>
                          Discovering...
                        </>
                      ) : (
                        <>
                          <span>✨</span>
                          Discover Channels
                        </>
                      )}
                    </button>
                  </div>

                  {discoveredChannels.length > 0 && (
                    <div className="mb-3 p-3 bg-[var(--panel)] rounded-lg border border-[var(--border)]">
                      <p className="text-xs text-[var(--muted)] mb-2 font-medium">AI Suggested Channels:</p>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {discoveredChannels.map((ch, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => addChannel(ch.handle)}
                            className="w-full text-left p-2 rounded hover:bg-[var(--panel2)] transition-colors border border-[var(--border)] hover:border-[var(--accent)]/40"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-[var(--fg)] mb-0.5">{ch.handle}</div>
                                <div className="text-xs text-[var(--muted)] line-clamp-2">{ch.reason}</div>
                              </div>
                              <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${
                                ch.confidence === 'high' ? 'bg-green-900/30 text-green-400' :
                                ch.confidence === 'medium' ? 'bg-yellow-900/30 text-yellow-400' :
                                'bg-gray-900/30 text-gray-400'
                              }`}>
                                {ch.confidence}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-[var(--muted)] mt-2 italic">Click a channel to add it below</p>
                    </div>
                  )}

                  <input
                    className={inputCls + " border-blue-800/40 focus:border-blue-500"}
                    placeholder="@python_jobs, @remotejobs, https://t.me/hr_breakfast (or click Discover)"
                    value={values.tg_channels}
                    onChange={(e) => setValue("tg_channels", e.target.value)}
                  />
                  <p className="text-xs text-[var(--muted)] mt-1 opacity-70">
                    Leave empty to skip Telegram. Add channels like @python_jobs, @remotejobs for better results.
                  </p>
                </div>
              )}

              {xlsxSelected && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted)] mb-2">
                    Lead list file
                  </p>
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`rounded-xl border-2 border-dashed px-4 py-8 text-center cursor-pointer transition-all ${
                      dragging
                        ? "border-[var(--accent)] bg-[var(--accent)]/5"
                        : xlsxFile
                        ? "border-[var(--green)] bg-[var(--green)]/10"
                        : "border-[var(--border)] hover:border-[var(--accent)]/40"
                    }`}
                  >
                    <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={handleFileChange} />
                    {xlsxFile ? (
                      <div>
                        <p className="text-[var(--green)] font-medium">✓ {xlsxFile.name}</p>
                        <p className="text-xs text-[var(--muted)] mt-1">{(xlsxFile.size / 1024).toFixed(1)} KB — click to replace</p>
                      </div>
                    ) : (
                      <div>
                        <Upload size={24} className="text-[var(--muted)] mx-auto mb-2" />
                        <p className="text-sm text-[var(--fg)]">Drop your XLSX / CSV here</p>
                        <p className="text-xs text-[var(--muted)] mt-1">Sales Navigator export, Apollo export, any lead list. Column names are auto-detected.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="flex gap-3">
                <Btn variant="ghost" onClick={() => setStep(0)} className="flex-1 justify-center">← Back</Btn>
                <Btn variant="primary" size="lg" className="flex-1 justify-center" onClick={() => { setError(null); setStep(2); }}>
                  Review & Launch →
                </Btn>
              </div>
            </div>
          )}

          {/* Step 3: Review & Launch */}
          {step === 2 && (
            <div className="grid gap-6">
              <div>
                <h3 className="font-title text-title-sm text-[var(--fg)] mb-4">Review Job Details</h3>
                <div className="space-y-3 p-4 bg-[var(--panel)] rounded-lg">
                  <div>
                    <p className="text-xs text-[var(--muted)] uppercase tracking-wider">Title</p>
                    <p className="text-sm text-[var(--fg)] font-medium">{values.title}</p>
                  </div>
                  {values.description && (
                    <div>
                      <p className="text-xs text-[var(--muted)] uppercase tracking-wider">Description</p>
                      <p className="text-sm text-[var(--fg)]">{values.description}</p>
                    </div>
                  )}
                  {values.skills && (
                    <div>
                      <p className="text-xs text-[var(--muted)] uppercase tracking-wider">Skills</p>
                      <p className="text-sm text-[var(--fg)]">{values.skills}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-[var(--muted)] uppercase tracking-wider">Sources</p>
                    <p className="text-sm text-[var(--fg)]">{values.sources.join(", ")}</p>
                  </div>
                  {values.sources.includes("telegram") && values.tg_channels && (
                    <div>
                      <p className="text-xs text-[var(--muted)] uppercase tracking-wider">Telegram Channels</p>
                      <p className="text-sm text-[var(--fg)]">{values.tg_channels}</p>
                    </div>
                  )}
                  {xlsxFile && (
                    <div>
                      <p className="text-xs text-[var(--muted)] uppercase tracking-wider">File</p>
                      <p className="text-sm text-[var(--fg)]">{xlsxFile.name}</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex gap-3">
                <Btn variant="ghost" onClick={() => setStep(1)} className="flex-1 justify-center">← Back</Btn>
                <Btn
                  variant="primary"
                  size="lg"
                  className="flex-1 justify-center"
                  onClick={handleSubmit}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? <Spinner /> : "Launch Pipeline 🚀"}
                </Btn>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* AI Vacancy Structuring Dialog */}
      {showStructureDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg shadow-2xl w-full max-w-md mx-4">
            <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap size={18} className="text-[var(--accent)]" />
                <h3 className="font-semibold text-[var(--fg)]">Structure with AI</h3>
              </div>
              <button
                onClick={() => {
                  setShowStructureDialog(false);
                  setRawVacancyText("");
                  setError(null);
                }}
                className="text-[var(--muted)] hover:text-[var(--fg)] transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <div className="p-4 space-y-4">
              <p className="text-sm text-[var(--muted)]">
                Paste a raw job description from any source (LinkedIn, email, Telegram, etc.) 
                and AI will extract structured fields automatically.
              </p>

              <div>
                <label className="text-sm font-medium text-[var(--fg2)] mb-2 block">
                  Raw vacancy text
                </label>
                <textarea
                  className={inputCls}
                  rows={8}
                  placeholder="Example:&#10;&#10;Looking for Sr. React dev, 5+ yrs exp, $150k-200k, SF Bay Area&#10;&#10;or&#10;&#10;Нужен middle Python разработчик, Django, PostgreSQL, удаленка"
                  value={rawVacancyText}
                  onChange={(e) => setRawVacancyText(e.target.value)}
                  autoFocus
                />
              </div>

              {error && (
                <div className="p-3 bg-red-900/10 border border-red-600 rounded-lg">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setShowStructureDialog(false);
                    setRawVacancyText("");
                    setError(null);
                  }}
                  className="flex-1 px-4 py-2 rounded-lg border border-[var(--border)] text-[var(--fg2)] hover:bg-[var(--panel2)] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleStructureVacancy}
                  disabled={structuring || !rawVacancyText.trim()}
                  className="flex-1 px-4 py-2 rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {structuring ? (
                    <>
                      <Spinner size="sm" />
                      Structuring...
                    </>
                  ) : (
                    <>
                      <Zap size={14} />
                      Structure
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
