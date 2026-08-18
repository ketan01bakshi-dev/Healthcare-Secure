"use client";

import PatientBar from "@/components/PatientBar";
import AppointmentScheduler from "@/components/AppointmentScheduler";
import { useI18n } from "@/lib/i18n";

export default function PatientAppointmentTab() {
  const { t } = useI18n();
  return (
    <div className="space-y-6 pt-4">
      <PatientBar />
      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-800 dark:text-slate-200">
          {t("appointments")}
        </h2>
        <AppointmentScheduler />
      </section>
    </div>
  );
}
