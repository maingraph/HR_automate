"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, API } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Field, inputCls } from "@/components/ui";
import { useForm } from "@/lib/hooks/useForm";
import {
  DEFAULT_TG_TEMPLATE,
  DEFAULT_LI_TEMPLATE,
  DEFAULT_QUESTIONS,
  DEFAULT_QUALIFICATION_NOTE,
} from "@/lib/templates";

type Job = { id: string; title: string };
type XlsxPreview = {
  columns: string[];
  sample_rows: Record<string, string>[];
  mapped_fields: Record<string, string>;
};

export default function NewCampaignPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<XlsxPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { values, setValue, isSubmitting, handleSubmit } = useForm({
    initialValues: {
      name: "FB Media Buyer — CIS",
      jobId: "",
      tgTemplate: DEFAULT_TG_TEMPLATE,
      liTemplate: DEFAULT_LI_TEMPLATE,
      questions: DEFAULT_QUESTIONS,
      tgAccount: "@maksimm2108",
      qualificationNote: DEFAULT_QUALIFICATION_NOTE,
    },
    validations: [
      {
        field: "name",
        validate: (v) => !v.trim() ? "Campaign name is required" : null,
      },
    ],
    onSubmit: async (formValues) => {
      setError(null);
      const campaign = await apiFetch<{ id: string }>("/outreach/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: formValues.name.trim(),
          job_id: formValues.jobId || undefined,
          tg_template: formValues.tgTemplate.trim() || undefined,
          li_template: formValues.liTemplate.trim() || undefined,
          screening_questions: formValues.questions.filter(Boolean),
          tg_account: formValues.tgAccount.trim() || undefined,
          qualification_note: formValues.qualificationNote.trim() || undefined,
        }),
      });

      if (file) {
        const fd = new FormData();
        fd.append("file", file);
        await fetch(`${API}/outreach/campaigns/${campaign.id}/import-xlsx`, {
          method: "POST",
          body: fd,
        });
      }

      router.push(`/outreach/${campaign.id}`);
    },
  });

  useEffect(() => {
    const loadJobs = async () => {
      try {
        const data = await apiFetch<Job[]>("/jobs");
        setJobs(data);
      } catch {
        // Silent fail
      }
    };
    loadJobs();
  }, []);

  const uploadPreview = useCallback(async (f: File) => {
    setPreviewLoading(true);
    setPreview(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await fetch(`${API}/outreach/leads/preview-xlsx`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data: XlsxPreview = await res.json();
      setPreview(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const handleFile = useCallback(
    (f: File | null) => {
      if (!f) return;
      setFile(f);
      uploadPreview(f);
    },
    [uploadPreview]
  );

  const addQuestion = () => setValue("questions", [...values.questions, ""]);
  const removeQuestion = (i: number) => setValue("questions", values.questions.filter((_, idx) => idx !== i));
  const updateQuestion = (i: number, v: string) =>
    setValue("questions", values.questions.map((s, idx) => (idx === i ? v : s)));

  const onSubmitWrapper = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await handleSubmit();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="grid gap-6 max-w-3xl">
      <section className="flex items-center gap-3">
        <a href="/outreach" className="text-sm text-[var(--muted)] hover:text-[var(--fg)]">
          Campaigns
        </a>
        <span className="text-[var(--muted)]">/</span>
        <h2 className="text-lg font-semibold">New campaign</h2>
      </section>

      <form onSubmit={onSubmitWrapper} className="grid gap-4 p-5 bg-[var(--panel)] border border-[var(--border)] rounded-xl">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Campaign name">
            <input
              className={inputCls}
              required
              value={values.name}
              onChange={(e) => setValue("name", e.target.value)}
              placeholder="e.g. FB Media Buyers May"
            />
          </Field>
          <Field label="Job vacancy">
            <select
              className={inputCls}
              value={values.jobId}
              onChange={(e) => setValue("jobId", e.target.value)}
            >
              <option value="">— select job —</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Sending account (Telegram)">
          <input
            className={inputCls}
            value={values.tgAccount}
            onChange={(e) => setValue("tgAccount", e.target.value)}
            placeholder="@username"
          />
        </Field>

        <Field label="Telegram message template">
          <textarea
            className={inputCls + " min-h-[280px]"}
            value={values.tgTemplate}
            onChange={(e) => setValue("tgTemplate", e.target.value)}
            placeholder="Hi {name}, I found your profile and thought you might be a great fit for…"
          />
        </Field>

        <Field label="LinkedIn message template">
          <textarea
            className={inputCls + " min-h-[100px]"}
            value={values.liTemplate}
            onChange={(e) => setValue("liTemplate", e.target.value)}
            placeholder="Hi {name}, I came across your LinkedIn profile and…"
          />
        </Field>

        <div className="grid gap-2">
          <span className="text-xs uppercase tracking-wide text-[var(--muted)]">Screening questions</span>
          {values.questions.map((q, i) => (
            <div key={i} className="flex gap-2">
              <input
                className={inputCls}
                value={q}
                onChange={(e) => updateQuestion(i, e.target.value)}
                placeholder={`Question ${i + 1}`}
              />
              {values.questions.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeQuestion(i)}
                  className="text-[var(--muted)] hover:text-red-400 px-2 text-sm transition-colors"
                >
                  Remove
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={addQuestion}
            className="text-sm text-[var(--accent)] text-left w-fit hover:opacity-80"
          >
            + Add question
          </button>
        </div>

        <Field label="Qualification — where to forward + criteria">
          <textarea
            className={inputCls + " min-h-[90px]"}
            value={values.qualificationNote}
            onChange={(e) => setValue("qualificationNote", e.target.value)}
            placeholder="Forward to @account — criteria for passing..."
          />
        </Field>

        <div className="grid gap-2">
          <span className="text-xs uppercase tracking-wide text-[var(--muted)]">Import leads from XLSX / CSV</span>
          <div
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
              dragging
                ? "border-[var(--accent)] bg-[var(--accent)]/5"
                : "border-[var(--border)] hover:border-[var(--accent)]/50"
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              handleFile(e.dataTransfer.files[0] ?? null);
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <div className="text-sm">
                <span className="font-medium">{file.name}</span>
                <span className="text-[var(--muted)] ml-2">({(file.size / 1024).toFixed(1)} KB)</span>
              </div>
            ) : (
              <p className="text-sm text-[var(--muted)]">
                Drag and drop a .csv or .xlsx file here, or click to browse
              </p>
            )}
          </div>

          {previewLoading && (
            <p className="text-xs text-[var(--muted)]">Parsing file…</p>
          )}

          {preview && (
            <div className="grid gap-2">
              <div className="flex gap-2 flex-wrap">
                {Object.entries(preview.mapped_fields).map(([col, field]) => (
                  <span key={col} className="text-[10px] px-2 py-0.5 bg-[#1b2028] rounded">
                    {col} <span className="text-[var(--accent)]">→ {field}</span>
                  </span>
                ))}
              </div>
              <div className="overflow-x-auto border border-[var(--border)] rounded-lg">
                <table className="w-full text-xs">
                  <thead className="bg-[#13171c] text-left text-[var(--muted)] uppercase">
                    <tr>
                      {preview.columns.map((col) => (
                        <th key={col} className="px-3 py-2 whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.sample_rows.map((row, i) => (
                      <tr key={i} className="border-t border-[var(--border)]">
                        {preview.columns.map((col) => (
                          <td key={col} className="px-3 py-2 truncate max-w-[160px]">
                            {row[col] ?? ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button
          disabled={isSubmitting}
          className="mt-2 bg-[var(--accent)] text-white rounded-lg py-2 font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {isSubmitting ? "Creating…" : "Create campaign"}
        </button>
      </form>
    </div>
  );
}
