"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { HOME_LANDING } from "@/lib/clinicRoutes";

export default function HomeRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(HOME_LANDING);
  }, [router]);
  return null;
}
