"use client";

import { useRouter } from "next/navigation";

import HomeShell from "@/components/home/HomeShell";
import PatientsList from "@/components/patients/PatientsList";
import { patientCardPath } from "@/lib/clinicRoutes";
import { useI18n } from "@/lib/i18n";

export default function SearchPage() {
  const { t } = useI18n();
  const router = useRouter();

  return (
    <HomeShell showFab={false} showNotification title={t("navSearch")}>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
        {t("universalSearchHint")}
      </p>
      <PatientsList
        onSelect={(id) => router.push(patientCardPath(id, "appointment"))}
      />
    </HomeShell>
  );
}
