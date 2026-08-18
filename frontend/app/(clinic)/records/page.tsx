"use client";

import DocumentUpload from "@/components/DocumentUpload";
import { useActiveClinicRole } from "@/components/DoctorGate";
import LabResultsForm from "@/components/LabResultsForm";
import NeedPatient from "@/components/NeedPatient";
import PatientAuditTrail from "@/components/PatientAuditTrail";
import PatientTimeline from "@/components/PatientTimeline";
import { useI18n } from "@/lib/i18n";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function RecordsPage() {
  const role = useActiveClinicRole();
  const router = useRouter();
  const { t } = useI18n();

  useEffect(() => {
    if (role === "lab") {
      router.replace("/labs/");
      return;
    }
    if (role === "receptionist") {
      router.replace("/today/");
    }
  }, [role, router]);

  if (role === "lab") {
    return null;
  }

  if (role === "receptionist") {
    return (
      <p className="text-sm text-slate-500">{t("redirectingToToday")}</p>
    );
  }

  return (
    <NeedPatient>
      <div className="space-y-6">
        <LabResultsForm />
        <DocumentUpload />
        <PatientTimeline />
        <PatientAuditTrail />
      </div>
    </NeedPatient>
  );
}
