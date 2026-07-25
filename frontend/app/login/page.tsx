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
  const [orgName, setOrgName] = useState("");
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
          : { email, password, org_name: orgName };

      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `${res.status} ${res.statusText}`);
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
    <div className="min-h-screen flex items-center justify-center bg-[#faf8ff] px-4">
      <div className="w-full max-w-md">
        {/* Logo + Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#15157d] text-white text-2xl font-bold mb-4 shadow-lg">
            S
          </div>
          <h1 className="text-3xl font-bold text-[#131b2e] mb-2" style={{ fontFamily: "Manrope" }}>
            Executive Talent Engine
          </h1>
          <p className="text-[#464652]" style={{ fontFamily: "Inter" }}>
            AI-powered recruitment sourcing
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-lg border border-[#c7c5d4] p-8 shadow-sm">
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

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-sm font-medium text-[#131b2e] mb-1.5" style={{ fontFamily: "Inter" }}>
                  Organization Name
                </label>
                <input
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 border border-[#c7c5d4] rounded-md focus:outline-none focus:ring-2 focus:ring-[#15157d] focus:border-transparent bg-white text-[#131b2e]"
                  style={{ fontFamily: "Inter" }}
                  placeholder="Acme Corp"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-[#131b2e] mb-1.5" style={{ fontFamily: "Inter" }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-[#c7c5d4] rounded-md focus:outline-none focus:ring-2 focus:ring-[#15157d] focus:border-transparent bg-white text-[#131b2e]"
                style={{ fontFamily: "Inter" }}
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[#131b2e] mb-1.5" style={{ fontFamily: "Inter" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full px-4 py-2.5 border border-[#c7c5d4] rounded-md focus:outline-none focus:ring-2 focus:ring-[#15157d] focus:border-transparent bg-white text-[#131b2e]"
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
              <div className="p-3 bg-[#ffdad6] border border-[#ba1a1a] rounded-md text-sm text-[#93000a]" style={{ fontFamily: "Inter" }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-[#15157d] text-white rounded-md font-semibold hover:bg-[#2e3192] focus:outline-none focus:ring-2 focus:ring-[#15157d] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
              style={{ fontFamily: "Inter" }}
            >
              {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
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
