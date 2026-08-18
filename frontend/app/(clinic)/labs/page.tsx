"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import DocumentUpload from "@/components/DocumentUpload";
import { useClinicFeatures } from "@/components/DoctorGate";
import LabResultsForm from "@/components/LabResultsForm";
import NeedPatient from "@/components/NeedPatient";
import PatientAttachments from "@/components/PatientAttachments";
import PendingLabOrders from "@/components/PendingLabOrders";
import { useI18n } from "@/lib/i18n";

export default function LabsPage() {
  const { t } = useI18n();
  const { has } = useClinicFeatures();
  const router = useRouter();
  const [suggestedTest, setSuggestedTest] = useState("");

  useEffect(() => {
    if (!has("labs")) {
      router.replace("/today/");
    }
  }, [has, router]);

  if (!has("labs")) {
    return (
      <p className="text-sm text-slate-500">
        Labs are not enabled for this clinic.
      </p>
    );
  }

  return (
    <NeedPatient>
      <div className="space-y-6">
        <p className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
          {t("labDeskHint")}
        </p>
        {has("obstetric") ? (
          <PendingLabOrders onSelectTest={setSuggestedTest} />
        ) : null}
        <LabResultsForm suggestedTest={suggestedTest} />
        <DocumentUpload labOnly />
        <PatientAttachments documentsOnly />
      </div>
    </NeedPatient>
  );
}
