"use client";

import { useClinicFeatures } from "@/components/DoctorGate";
import EncounterWorkspace from "@/components/EncounterWorkspace";
import ForwardCaseHistory from "@/components/ForwardCaseHistory";
import PatientCaseBrief from "@/components/PatientCaseBrief";
import PatientVitalsCharts from "@/components/PatientVitalsCharts";
import ReferralInboxBanner from "@/components/ReferralInboxBanner";
import RecommendedDiagnostics from "@/components/RecommendedDiagnostics";
import VideoConsultPanel from "@/components/VideoConsultPanel";

export default function PatientVisitTab() {
  const { has } = useClinicFeatures();
  return (
    <div className="space-y-6 pt-4">
      <ReferralInboxBanner />
      <PatientVitalsCharts />
      {has("obstetric") ? <PatientCaseBrief /> : null}
      {has("video_consult") ? <VideoConsultPanel /> : null}
      {has("obstetric") ? <RecommendedDiagnostics /> : null}
      <EncounterWorkspace />
      <ForwardCaseHistory />
    </div>
  );
}
