"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import AppHeader from "@/components/home/AppHeader";
import PatientAppointmentTab from "@/components/patient-card/PatientAppointmentTab";
import PatientCardHeader from "@/components/patient-card/PatientCardHeader";
import PatientInnerTabs from "@/components/patient-card/PatientInnerTabs";
import PatientRecordsTab from "@/components/patient-card/PatientRecordsTab";
import PatientVisitTab from "@/components/patient-card/PatientVisitTab";
import PatientVitalsTab from "@/components/patient-card/PatientVitalsTab";
import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import type { PatientCardTab } from "@/lib/clinicRoutes";
import { useI18n } from "@/lib/i18n";
import { usePatient } from "@/context/PatientContext";

export default function PatientCardPage() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const patientId = searchParams.get("id");
  const tab = (searchParams.get("tab") || "appointment") as PatientCardTab;
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const { lockFromDirectory } = usePatient();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) {
      router.replace("/home/patients/");
      return;
    }
    setLoading(true);
    setError(null);
    void lockFromDirectory(patientId)
      .then(() => setLoading(false))
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : t("openPatientFailed"));
        setLoading(false);
      });
  }, [patientId, lockFromDirectory, router, t]);

  if (!patientId) return null;

  if (loading) {
    return (
      <p className="text-sm text-slate-500">{t("loadingPatients")}</p>
    );
  }

  if (error) {
    return (
      <div>
        <AppHeader onMenuClick={() => router.back()} title={t("patient")} />
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      </div>
    );
  }

  function renderTab() {
    if (tab === "vitals") {
      if (role === "receptionist" || role === "lab") {
        return <p className="text-sm text-slate-500">{t("staffVisitHint")}</p>;
      }
      return <PatientVitalsTab />;
    }
    if (tab === "records") {
      if (role === "receptionist" || role === "lab") {
        return <p className="text-sm text-slate-500">{t("selectPatientFirst")}</p>;
      }
      return <PatientRecordsTab />;
    }
    if (tab === "visit") {
      if (role !== "doctor" || !has("voice_rx")) {
        return <p className="text-sm text-slate-500">{t("staffVisitHint")}</p>;
      }
      return <PatientVisitTab />;
    }
    return <PatientAppointmentTab />;
  }

  return (
    <div className="pb-8">
      <AppHeader
        onMenuClick={() => router.push("/home/patients/")}
        title={t("patient")}
      />
      <PatientCardHeader />
      <PatientInnerTabs blindPatientId={patientId} />
      {renderTab()}
    </div>
  );
}
