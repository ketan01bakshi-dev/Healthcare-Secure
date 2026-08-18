"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function MoreLegacyRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/home/profile/");
  }, [router]);
  return <p className="text-sm text-slate-500">Loading…</p>;
}
