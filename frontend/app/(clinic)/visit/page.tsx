"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import EncounterWorkspace from "@/components/EncounterWorkspace";
import ForwardCaseHistory from "@/components/ForwardCaseHistory";
import NeedPatient from "@/components/NeedPatient";
import PatientCaseBrief from "@/components/PatientCaseBrief";
import PatientVitalsCharts from "@/components/PatientVitalsCharts";
import ReferralInboxBanner from "@/components/ReferralInboxBanner";
import VideoConsultPanel from "@/components/VideoConsultPanel";
import RecommendedDiagnostics from "@/components/RecommendedDiagnostics";
import { useI18n } from "@/lib/i18n";

export default function VisitPage() {
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const router = useRouter();
  const { t } = useI18n();

  useEffect(() => {
    if (role === "lab") {
      router.replace("/labs/");
      return;
    }
    if (role === "staff" || role === "receptionist") {
      router.replace("/today/");
      return;
    }
    if (!has("voice_rx") && role === "doctor") {
      router.replace("/today/");
    }
  }, [role, router, has]);

  if (role === "lab") {
    return (
      <p className="text-sm text-slate-500">{t("redirectingToLabs")}</p>
    );
  }

  if (role === "staff" || role === "receptionist") {
    return (
      <p className="text-sm text-slate-500">{t("redirectingToToday")}</p>
    );
  }

  if (!has("voice_rx")) {
    return (
      <p className="text-sm text-slate-500">
        Voice prescription is not enabled for this clinic.
      </p>
    );
  }

  return (
    <NeedPatient>
      <div className="space-y-6">
        <ReferralInboxBanner />
        <PatientVitalsCharts />
        {has("obstetric") ? <PatientCaseBrief /> : null}
        {has("video_consult") ? <VideoConsultPanel /> : null}
        {has("obstetric") ? <RecommendedDiagnostics /> : null}
        <EncounterWorkspace />
        <ForwardCaseHistory />
      </div>
    </NeedPatient>
  );
}
