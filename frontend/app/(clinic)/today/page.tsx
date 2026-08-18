"use client";

import AllPatientsDirectory from "@/components/AllPatientsDirectory";
import AppointmentScheduler from "@/components/AppointmentScheduler";
import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import OfflineSyncBanner from "@/components/OfflineSyncBanner";
import PatientBilling from "@/components/PatientBilling";
import ReferralInboxBanner from "@/components/ReferralInboxBanner";
import WaitingQueue from "@/components/WaitingQueue";
import { usePatient } from "@/context/PatientContext";
import { useI18n } from "@/lib/i18n";

export default function TodayPage() {
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const { locked } = usePatient();
  const { t } = useI18n();

  if (role === "lab") {
    return (
      <div className="space-y-6">
        <OfflineSyncBanner />
        <section className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-sky-900">
            {t("navToday")}
          </h2>
          <p className="mt-2 text-sm text-sky-950">{t("labTodayHint")}</p>
        </section>
        <AllPatientsDirectory />
      </div>
    );
  }

  const showBilling =
    locked &&
    (role === "doctor" || role === "staff" || role === "receptionist");

  return (
    <div className="space-y-6">
      <OfflineSyncBanner />
      <ReferralInboxBanner />
      {has("appointments") ? <AppointmentScheduler /> : null}
      {has("queue") ? <WaitingQueue /> : null}
      <AllPatientsDirectory />
      {showBilling ? <PatientBilling /> : null}
    </div>
  );
}
