"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/api";
import { saveAuth, type AuthResponse } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const registrationEnabled = process.env.NEXT_PUBLIC_ALLOW_REGISTRATION !== "false";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const body =
        mode === "login"
          ? { email, password }
          : { email, password, org_name: `${email.split("@")[0] || "My"} workspace` };

      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        let message = `${res.status} ${res.statusText}`;
        try {
          message = JSON.parse(text).detail || message;
        } catch {}
        throw new Error(message);
      }

      const data: AuthResponse = await res.json();
      saveAuth(data);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)] px-4">
      <div className="w-full max-w-md">
        {/* Logo + Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[var(--accent)] text-white text-2xl font-bold mb-4 shadow-lg">
            S
          </div>
          <h1 className="text-3xl font-bold text-[#131b2e] mb-2" style={{ fontFamily: "Manrope" }}>
            Sourcer
          </h1>
          <p className="text-[#464652]" style={{ fontFamily: "Inter" }}>
            Sign in or create your private sourcing workspace
          </p>
        </div>

        {/* Card */}
        <div className="bg-[var(--surface)] rounded-xl border border-[var(--border)] p-8 shadow-sm">
          {/* Mode Toggle */}
          {registrationEnabled && <div className="flex gap-2 mb-6 p-1 bg-[#f2f3ff] rounded-lg">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                mode === "login"
                  ? "bg-white text-[#15157d] shadow-sm"
                  : "text-[#464652] hover:text-[#131b2e]"
              }`}
              style={{ fontFamily: "Inter" }}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setMode("register")}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                mode === "register"
                  ? "bg-white text-[#15157d] shadow-sm"
                  : "text-[#464652] hover:text-[#131b2e]"
              }`}
              style={{ fontFamily: "Inter" }}
            >
              Register
            </button>
          </div>}

          {mode === "register" && <p className="text-sm text-[var(--muted)] mb-4">Workspace creates automatically from your email.</p>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--fg)] mb-1.5" style={{ fontFamily: "Inter" }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-[var(--border)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent bg-[var(--panel)] text-[var(--fg)]"
                style={{ fontFamily: "Inter" }}
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--fg)] mb-1.5" style={{ fontFamily: "Inter" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full px-4 py-2.5 border border-[var(--border)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent bg-[var(--panel)] text-[var(--fg)]"
                style={{ fontFamily: "Inter" }}
                placeholder="••••••••"
              />
              {mode === "register" && (
                <p className="text-xs text-[#464652] mt-1" style={{ fontFamily: "Inter" }}>
                  Minimum 8 characters
                </p>
              )}
            </div>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/40 rounded-md text-sm text-red-300" style={{ fontFamily: "Inter" }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-[var(--accent)] text-white rounded-md font-semibold hover:bg-[var(--accent-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
              style={{ fontFamily: "Inter" }}
            >
              {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create workspace"}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-[#777683] mt-6" style={{ fontFamily: "Inter" }}>
          Sourcer v0.2.0 · Secure authentication
        </p>
      </div>
    </div>
  );
}
