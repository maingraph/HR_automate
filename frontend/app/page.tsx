"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated()) {
      router.push("/dashboard");
    } else {
      router.push("/login");
    }
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center">
        <div className="w-16 h-16 border-4 border-[#15157d] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <div className="text-[#464652]" style={{ fontFamily: "Inter" }}>Loading...</div>
      </div>
    </div>
  );
}
