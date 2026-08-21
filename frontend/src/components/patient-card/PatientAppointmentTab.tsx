"use client";

import AppointmentScheduler from "@/components/AppointmentScheduler";
import PatientBar from "@/components/PatientBar";
import PatientBilling from "@/components/PatientBilling";
import { useActiveClinicRole } from "@/components/DoctorGate";
import { useI18n } from "@/lib/i18n";

export default function PatientAppointmentTab() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const showBilling =
    role === "doctor" || role === "staff" || role === "receptionist";

  return (
    <div className="space-y-6 pt-4">
      <PatientBar title={t("details")} />
      <AppointmentScheduler />
      {showBilling ? <PatientBilling /> : null}
    </div>
  );
}
