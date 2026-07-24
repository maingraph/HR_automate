"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Btn, Card, Field, PageHeader, Spinner, inputCls, Badge } from "@/components/ui";
import { Eye, EyeOff, Save, AlertTriangle, CheckCircle, Key, Cookie, MessageSquare } from "lucide-react";

type Creds = {
  li_at_cookie?: string;
  li_at_status?: "valid" | "expired" | "unknown";
  li_at_set_at?: string;
  tg_session_exists?: boolean;
  openrouter_key_set?: boolean;
  gemini_key_set?: boolean;
  operator_tg_username?: string;
  li_send_min_delay?: number;
  li_send_max_delay?: number;
  li_headless?: boolean;
};

type Section = "linkedin" | "telegram" | "ai" | "settings";

export default function CredentialsPage() {
  const [creds, setCreds]       = useState<Creds>({});
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState<Section | null>(null);
  const [saved, setSaved]       = useState<Section | null>(null);
  const [showCookie, setShowCookie] = useState(false);

  // LinkedIn form state
  const [liCookie, setLiCookie] = useState("");
  const [liMinDelay, setLiMinDelay] = useState("30");
  const [liMaxDelay, setLiMaxDelay] = useState("90");
  const [liHeadless, setLiHeadless] = useState(true);

  // AI / API keys form state
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [geminiKey, setGeminiKey]         = useState("");

  // Settings form state
  const [operatorTg, setOperatorTg] = useState("");

  // Model configuration state
  const [aiProvider, setAiProvider] = useState<"gemini" | "openrouter">("gemini");
  const [models, setModels] = useState({
    job_planning: "",
    scoring: "",
    vacancy_structure: "",
    outreach_classify: "",
    outreach_draft: "",
    channel_discovery: "",
  });
  const [availableModels, setAvailableModels] = useState<{
    gemini: string[];
    openrouter: string[];
  }>({
    gemini: [],
    openrouter: []
  });

  useEffect(() => {
    const loadCredentials = async () => {
      try {
        const data = await apiFetch<Creds>("/admin/credentials");
        setCreds(data);
        setLiMinDelay(String(data.li_send_min_delay ?? 30));
        setLiMaxDelay(String(data.li_send_max_delay ?? 90));
        setLiHeadless(data.li_headless ?? true);
        setOperatorTg(data.operator_tg_username ?? "");
      } catch {
        // Silent fail
      } finally {
        setLoading(false);
      }
    };
    
    const loadModels = async () => {
      try {
        const data = await apiFetch<any>("/admin/models");
        setAiProvider(data.ai_provider);
        setAvailableModels(data.available_models);
        setModels({
          job_planning: data.current_models.job_planning || "",
          scoring: data.current_models.scoring || "",
          vacancy_structure: data.current_models.vacancy_structure || "",
          outreach_classify: data.current_models.outreach_classify || "",
          outreach_draft: data.current_models.outreach_draft || "",
          channel_discovery: data.current_models.channel_discovery || "",
        });
      } catch (err) {
        console.error("Failed to load model config:", err);
      }
    };
    
    loadCredentials();
    loadModels();
  }, []);

  const save = async (section: Section, body: Record<string, unknown>) => {
    setSaving(section);
    try {
      await apiFetch("/admin/credentials", {
        method: "PATCH",
        body: JSON.stringify({ section, ...body }),
      });
    } catch {
      // Silent fail
    }
    setSaving(null);
    setSaved(section);
    setTimeout(() => setSaved(null), 2500);
    // Reload to get fresh status
    try {
      const fresh = await apiFetch<Creds>("/admin/credentials");
      setCreds(fresh);
    } catch {
      // Keep existing creds on error
    }
  };

  const saveModels = async () => {
    setSaving("ai");
    try {
      await apiFetch("/admin/models", {
        method: "PATCH",
        body: JSON.stringify({
          ai_provider: aiProvider,
          models: models
        })
      });
      setSaved("ai");
      setTimeout(() => setSaved(null), 2500);
    } catch (err) {
      console.error("Failed to save model config:", err);
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-24"><Spinner size="lg" /></div>;
  }

  return (
    <div className="grid gap-6 max-w-3xl">
      <PageHeader
        title="Credentials Manager"
        subtitle="Manage API keys, cookies, and agent settings. All values are stored in your server .env — never in the database."
      />

      {/* ── LinkedIn ──────────────────────────────────────────────────── */}
      <Card className="p-5 grid gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cookie size={16} className="text-blue-400" />
            <h2 className="font-semibold">LinkedIn Cookie</h2>
          </div>
          {creds.li_at_status === "expired" ? (
            <Badge variant="rejected"><AlertTriangle size={11} /> Cookie expired</Badge>
          ) : creds.li_at_status === "valid" ? (
            <Badge variant="active"><CheckCircle size={11} /> Valid</Badge>
          ) : (
            <Badge variant="default">Unknown</Badge>
          )}
        </div>

        {creds.li_at_set_at && (
          <p className="text-xs text-[var(--muted)]">Last updated: {new Date(creds.li_at_set_at).toLocaleString()}</p>
        )}

        <div className="bg-amber-950/30 border border-amber-800/40 rounded-lg px-3 py-2.5 text-xs text-amber-300 flex gap-2">
          <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />
          <span>
            The <code className="font-mono bg-amber-900/40 px-1 rounded">li_at</code> cookie expires randomly, especially from new IPs.
            When expired, the agent will send you a Telegram alert automatically.
            Log into linkedin.com, open DevTools → Application → Cookies, copy the <code className="font-mono bg-amber-900/40 px-1 rounded">li_at</code> value, and paste it here.
          </span>
        </div>

        <Field label="li_at cookie value">
          <div className="relative">
            <input
              className={inputCls + " pr-10 font-mono text-xs"}
              type={showCookie ? "text" : "password"}
              placeholder="AQEDATiB… (paste your li_at cookie)"
              value={liCookie}
              onChange={(e) => setLiCookie(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setShowCookie(!showCookie)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--muted)] hover:text-[var(--fg)]"
            >
              {showCookie ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
        </Field>

        <div className="grid grid-cols-3 gap-3">
          <Field label="Min delay (s)" hint="Between messages">
            <input
              type="number"
              className={inputCls}
              value={liMinDelay}
              onChange={(e) => setLiMinDelay(e.target.value)}
              min={10}
            />
          </Field>
          <Field label="Max delay (s)">
            <input
              type="number"
              className={inputCls}
              value={liMaxDelay}
              onChange={(e) => setLiMaxDelay(e.target.value)}
              min={10}
            />
          </Field>
          <Field label="Headless browser">
            <div className="flex items-center gap-2 h-9">
              <button
                type="button"
                onClick={() => setLiHeadless(!liHeadless)}
                className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${liHeadless ? "bg-[var(--accent)]" : "bg-[var(--border2)]"}`}
              >
                <div className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${liHeadless ? "translate-x-4" : "translate-x-0"}`} />
              </button>
              <span className="text-xs text-[var(--fg2)]">{liHeadless ? "Headless" : "Visible"}</span>
            </div>
          </Field>
        </div>

        <Btn
          variant="primary"
          loading={saving === "linkedin"}
          onClick={() => save("linkedin", { li_at: liCookie, li_send_min_delay: +liMinDelay, li_send_max_delay: +liMaxDelay, li_headless: liHeadless })}
        >
          {saved === "linkedin" ? <><CheckCircle size={13} /> Saved!</> : <><Save size={13} /> Save LinkedIn settings</>}
        </Btn>
      </Card>

      {/* ── Telegram ─────────────────────────────────────────────────── */}
      <Card className="p-5 grid gap-4">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} className="text-blue-400" />
          <h2 className="font-semibold">Telegram Session</h2>
          {creds.tg_session_exists ? (
            <Badge variant="active">Session active</Badge>
          ) : (
            <Badge variant="rejected">No session</Badge>
          )}
        </div>

        <div className="bg-[var(--panel2)] border border-[var(--border)] rounded-lg px-4 py-3 text-sm text-[var(--fg2)]">
          <p className="font-medium mb-1">How to authenticate Telegram:</p>
          <ol className="list-decimal list-inside space-y-1 text-xs text-[var(--muted)]">
            <li>Make sure <code className="font-mono bg-[var(--panel)] px-1 rounded">TELEGRAM_API_ID</code>, <code className="font-mono bg-[var(--panel)] px-1 rounded">TELEGRAM_API_HASH</code>, and <code className="font-mono bg-[var(--panel)] px-1 rounded">TELEGRAM_PHONE</code> are set in your <code className="font-mono">.env</code> file.</li>
            <li>From the project root, run: <code className="font-mono bg-[var(--panel)] px-1 rounded">cd backend && python ../scripts/telegram_login.py</code></li>
            <li>Enter the verification code sent to your phone.</li>
            <li>A <code className="font-mono bg-[var(--panel)] px-1 rounded">sourcer.session</code> file will be created in <code className="font-mono">data/</code>.</li>
            <li>The Telegram listener will use this session automatically on next launch.</li>
          </ol>
        </div>

        <Field label="Operator Telegram username" hint="This account gets pinged when the li_at cookie expires or the agent needs attention">
          <input
            className={inputCls}
            placeholder="@yourusername"
            value={operatorTg}
            onChange={(e) => setOperatorTg(e.target.value)}
          />
        </Field>

        <Btn
          variant="primary"
          loading={saving === "settings"}
          onClick={() => save("settings", { operator_tg_username: operatorTg })}
        >
          {saved === "settings" ? <><CheckCircle size={13} /> Saved!</> : <><Save size={13} /> Save settings</>}
        </Btn>
      </Card>

      {/* ── AI / API Keys ─────────────────────────────────────────────── */}
      <Card className="p-5 grid gap-4">
        <div className="flex items-center gap-2">
          <Key size={16} className="text-purple-400" />
          <h2 className="font-semibold">AI Provider Keys</h2>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--muted)]">OpenRouter</span>
            {creds.openrouter_key_set ? (
              <Badge variant="active">Set</Badge>
            ) : (
              <Badge variant="rejected">Not set</Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--muted)]">Gemini</span>
            {creds.gemini_key_set ? (
              <Badge variant="active">Set</Badge>
            ) : (
              <Badge variant="rejected">Not set</Badge>
            )}
          </div>
        </div>

        <Field label="OpenRouter API key" hint="Used for intent classification and reply drafting">
          <input
            className={inputCls + " font-mono text-xs"}
            type="password"
            placeholder="sk-or-… (leave blank to keep existing)"
            value={openrouterKey}
            onChange={(e) => setOpenrouterKey(e.target.value)}
          />
        </Field>

        <Field label="Gemini API key" hint="Used for candidate scoring and embedding">
          <input
            className={inputCls + " font-mono text-xs"}
            type="password"
            placeholder="AIzaSy… (leave blank to keep existing)"
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
          />
        </Field>

        <Btn
          variant="primary"
          loading={saving === "ai"}
          onClick={() => save("ai", { openrouter_key: openrouterKey || undefined, gemini_key: geminiKey || undefined })}
        >
          {saved === "ai" ? <><CheckCircle size={13} /> Saved!</> : <><Save size={13} /> Save API keys</>}
        </Btn>
      </Card>

      {/* ── AI Model Configuration ─────────────────────────────────────── */}
      <Card className="p-5 grid gap-4">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-purple-400">psychology</span>
          <h2 className="font-semibold">AI Model Configuration</h2>
        </div>

        <div className="bg-[var(--panel2)] border border-[var(--border)] rounded-lg px-4 py-3 text-sm text-[var(--fg2)]">
          <p className="mb-2">Configure which AI models are used for different tasks. Each task can use a different model for optimal cost/performance.</p>
          <p className="text-xs text-[var(--muted)]">
            💡 Tip: Use a low-cost model such as gemini-2.5-flash-lite for high-volume scoring,
            and gemini-2.5-pro only when a task needs deeper reasoning.
          </p>
        </div>

        {/* Provider Selection */}
        <Field label="Default AI Provider">
          <select 
            className={inputCls}
            value={aiProvider}
            onChange={(e) => setAiProvider(e.target.value as "gemini" | "openrouter")}
          >
            <option value="gemini">Gemini (Direct API)</option>
            <option value="openrouter">OpenRouter (Multi-model proxy)</option>
          </select>
        </Field>

        {/* Task-specific model selection */}
        <div className="grid gap-3">
          <Field label="Job Planning" hint="Generate LinkedIn query, Telegram keywords, scoring rubric">
            <select 
              className={inputCls}
              value={models.job_planning}
              onChange={(e) => setModels({...models, job_planning: e.target.value})}
            >
              <option value="">Use default ({aiProvider === "gemini" ? "gemini-2.5-flash-lite" : "google/gemini-2.5-flash-lite"})</option>
              {availableModels[aiProvider].map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </Field>

          <Field label="Candidate Scoring" hint="Score candidates 0-100 based on rubric">
            <select 
              className={inputCls}
              value={models.scoring}
              onChange={(e) => setModels({...models, scoring: e.target.value})}
            >
              <option value="">Use default</option>
              {availableModels[aiProvider].map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </Field>

          <Field label="Vacancy Structuring" hint="Extract structured data from raw job descriptions">
            <select 
              className={inputCls}
              value={models.vacancy_structure}
              onChange={(e) => setModels({...models, vacancy_structure: e.target.value})}
            >
              <option value="">Use default</option>
              {availableModels[aiProvider].map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </Field>

          <Field label="Outreach Classification" hint="Classify candidate reply intent">
            <select 
              className={inputCls}
              value={models.outreach_classify}
              onChange={(e) => setModels({...models, outreach_classify: e.target.value})}
            >
              <option value="">Use default</option>
              {availableModels[aiProvider].map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </Field>

          <Field label="Outreach Drafting" hint="Generate reply drafts to candidates">
            <select 
              className={inputCls}
              value={models.outreach_draft}
              onChange={(e) => setModels({...models, outreach_draft: e.target.value})}
            >
              <option value="">Use default</option>
              {availableModels[aiProvider].map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </Field>

          <Field label="Channel Discovery" hint="Discover relevant Telegram channels">
            <select 
              className={inputCls}
              value={models.channel_discovery}
              onChange={(e) => setModels({...models, channel_discovery: e.target.value})}
            >
              <option value="">Use default</option>
              {availableModels[aiProvider].map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </Field>
        </div>

        <Btn
          variant="primary"
          loading={saving === "ai"}
          onClick={saveModels}
        >
          {saved === "ai" ? <><CheckCircle size={13} /> Saved!</> : <><Save size={13} /> Save Model Configuration</>}
        </Btn>
      </Card>
    </div>
  );
}
