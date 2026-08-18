"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/today/");
  }, [router]);
  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-4">
      <p className="text-sm text-slate-500">Loading…</p>
    </main>
  );
}
