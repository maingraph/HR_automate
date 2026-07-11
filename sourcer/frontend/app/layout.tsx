"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { getUser, clearAuth } from "@/lib/auth";
import "./globals.css";

// Preload fonts for Executive Talent Engine design system
const fontsPreload = () => (
  <>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@600;700;800&display=swap" rel="stylesheet" />
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
  </>
);

// Sidebar items map to REAL routes only — no dead links.
const NAV_SECTIONS: { items: { href: string; label: string; icon: string }[] }[] = [
  {
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
      { href: "/jobs/new", label: "New Job", icon: "add_circle" },
    ],
  },
  {
    items: [
      { href: "/outreach", label: "Outreach", icon: "send" },
      { href: "/outreach/inbox", label: "Inbox", icon: "inbox" },
      { href: "/outreach/review", label: "Review Queue", icon: "rule" },
    ],
  },
  {
    items: [
      { href: "/admin/logs", label: "Logs", icon: "monitoring" },
      { href: "/admin/credentials", label: "Credentials", icon: "key" },
    ],
  },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = getUser();
  const isLoginPage = pathname === "/login";
  const [query, setQuery] = useState("");

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    router.push(q ? `/dashboard?q=${encodeURIComponent(q)}` : "/dashboard");
  }

  function isActive(href: string) {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <html lang="en">
      <head>{fontsPreload()}</head>
      <body className="min-h-screen bg-[var(--background)] text-[var(--fg)]">
        {isLoginPage ? (
          <main className="min-h-screen">{children}</main>
        ) : (
          <div className="flex min-h-screen">
            {/* Sidebar */}
            <aside className="hidden md:flex w-60 shrink-0 flex-col sticky top-0 h-screen border-r border-[var(--border)] bg-[var(--surface)]">
              <div className="px-5 h-16 flex items-center gap-3 border-b border-[var(--border)]">
                <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-white font-bold text-sm shadow-lg glow-accent">
                  S
                </div>
                <div className="leading-tight">
                  <div className="font-semibold tracking-tight text-[var(--fg)]">Sourcer</div>
                  <div className="text-[10px] text-[var(--muted)]">Recruitment Suite</div>
                </div>
              </div>

              <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-4">
                {NAV_SECTIONS.map((section, i) => (
                  <div key={i} className="space-y-1">
                    {i > 0 && <div className="h-px bg-[var(--border)] mx-2 mb-3" />}
                    {section.items.map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                          isActive(item.href)
                            ? "bg-[var(--panel2)] text-[var(--fg)] font-medium"
                            : "text-[var(--fg2)] hover:text-[var(--fg)] hover:bg-[var(--panel)]"
                        }`}
                      >
                        <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                        {item.label}
                      </Link>
                    ))}
                  </div>
                ))}
              </nav>

              <div className="px-3 py-3 border-t border-[var(--border)] flex items-center gap-2 text-[10px] text-[var(--muted)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--green)] pulse-dot" />
                Agent running
                <span className="ml-auto">v0.2.0</span>
              </div>
            </aside>

            {/* Content column */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Top bar */}
              <header className="sticky top-0 z-40 glass px-6 h-16 flex items-center gap-4">
                <form onSubmit={handleSearch} className="flex-1 max-w-xl relative">
                  <span className="material-symbols-outlined text-[20px] text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none">
                    search
                  </span>
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search jobs across Sourcer…"
                    className="input w-full pl-10"
                    aria-label="Search jobs"
                  />
                </form>

                <button
                  onClick={() => router.push("/jobs/new")}
                  className="btn-primary hidden sm:flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[18px]">add</span>
                  New Job
                </button>

                <ThemeToggle />

                {user && (
                  <div className="flex items-center gap-2 pl-2 border-l border-[var(--border)]">
                    <span className="text-xs text-[var(--muted)] hidden lg:block">{user.email}</span>
                    <button
                      onClick={handleLogout}
                      className="text-xs text-[var(--fg2)] hover:text-[var(--fg)] underline"
                    >
                      Logout
                    </button>
                  </div>
                )}
              </header>

              {/* Page content */}
              <main className="flex-1 px-6 lg:px-8 py-8 max-w-[1400px] w-full mx-auto">
                {children}
              </main>

              {/* Footer */}
              <footer className="border-t border-[var(--border)] px-6 py-3 text-[10px] text-[var(--muted)] flex items-center gap-3 bg-[var(--surface)]">
                <span>Sourcer v0.2.0</span>
                {user?.org_name && (
                  <>
                    <span>·</span>
                    <span>{user.org_name}</span>
                  </>
                )}
              </footer>
            </div>
          </div>
        )}
      </body>
    </html>
  );
}
