"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { HOME_LANDING } from "@/lib/clinicRoutes";

export default function TodayRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(HOME_LANDING);
  }, [router]);
  return (
    <p className="text-sm text-slate-500">Loading…</p>
  );
}
