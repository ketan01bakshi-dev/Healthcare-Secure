"use client";

import HomeShell from "@/components/home/HomeShell";
import PatientsList from "@/components/patients/PatientsList";
import { useI18n } from "@/lib/i18n";

export default function PatientsPage() {
  const { t } = useI18n();
  return (
    <HomeShell showFab showNotification title={t("navPatients")}>
      <PatientsList />
    </HomeShell>
  );
}
