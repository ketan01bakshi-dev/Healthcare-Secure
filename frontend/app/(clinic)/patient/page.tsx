"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { usePatient } from "@/context/PatientContext";
import { patientCardPath } from "@/lib/clinicRoutes";

export default function PatientLegacyRedirect() {
  const router = useRouter();
  const { blindPatientId, locked } = usePatient();

  useEffect(() => {
    if (locked && blindPatientId) {
      router.replace(patientCardPath(blindPatientId, "vitals"));
    } else {
      router.replace("/home/patients/");
    }
  }, [router, locked, blindPatientId]);

  return <p className="text-sm text-slate-500">Loading…</p>;
}
