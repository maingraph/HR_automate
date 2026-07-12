"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

/**
 * Auth guard: redirect to /login if not authenticated.
 * Wrap pages that require auth.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!isAuthenticated() && pathname !== "/login") {
      router.replace("/login");
    }
    setChecked(true);
  }, [pathname, router]);

  if (pathname !== "/login" && (!checked || !isAuthenticated())) {
    return null;
  }

  return <>{children}</>;
}
