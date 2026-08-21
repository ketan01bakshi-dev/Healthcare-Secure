"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import AppHeader from "@/components/home/AppHeader";
import PatientAppointmentTab from "@/components/patient-card/PatientAppointmentTab";
import PatientCardHeader from "@/components/patient-card/PatientCardHeader";
import PatientInnerTabs from "@/components/patient-card/PatientInnerTabs";
import PatientRecordsTab from "@/components/patient-card/PatientRecordsTab";
import PatientVisitTab from "@/components/patient-card/PatientVisitTab";
import PatientVitalsTab from "@/components/patient-card/PatientVitalsTab";
import NotificationToast from "@/components/home/NotificationToast";
import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import type { PatientCardTab } from "@/lib/clinicRoutes";
import { patientCardPath } from "@/lib/clinicRoutes";
import { useSwipeTabs } from "@/hooks/useSwipeTabs";
import { patientTabsForRole } from "@/lib/tabOrder";
import { lightHaptic } from "@/lib/haptics";
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

  const visibleTabs = useMemo(
    () => patientTabsForRole(role, has),
    [role, has],
  );

  const onSwipeTab = useCallback(
    (next: string) => {
      if (!patientId || next === tab) return;
      lightHaptic();
      router.push(patientCardPath(patientId, next as PatientCardTab));
    },
    [patientId, router, tab],
  );

  const swipe = useSwipeTabs({
    items: visibleTabs,
    active: tab,
    onChange: onSwipeTab,
  });

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

  const backButton = (
    <button
      aria-label={t("back")}
      className="flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 text-slate-700 dark:border-slate-600 dark:text-slate-200"
      onClick={() => router.push("/home/patients/")}
      type="button"
    >
      ←
    </button>
  );

  if (loading) {
    return (
      <p className="text-sm text-slate-500">{t("loadingPatients")}</p>
    );
  }

  if (error) {
    return (
      <div>
        <AppHeader leading={backButton} showMenu={false} title={t("patient")} />
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
    <div className="pb-8" {...swipe}>
      <AppHeader leading={backButton} showMenu={false} title={t("patient")} />
      <PatientInnerTabs blindPatientId={patientId} />
      <PatientCardHeader />
      {renderTab()}
      <NotificationToast className="bottom-6" />
    </div>
  );
}
