"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

/**
 * Auth guard: redirect to /login if not authenticated.
 * Wrap pages that require auth.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isAuthenticated() && pathname !== "/login") {
      router.push("/login");
    }
  }, [pathname, router]);

  if (!isAuthenticated() && pathname !== "/login") {
    return null; // Don't render until redirect
  }

  return <>{children}</>;
}
