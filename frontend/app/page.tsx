"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { HOME_LANDING } from "@/lib/clinicRoutes";

export default function HomePage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(HOME_LANDING);
  }, [router]);
  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-4 dark:bg-slate-950">
      <p className="text-sm text-slate-500">Loading…</p>
    </main>
  );
}
