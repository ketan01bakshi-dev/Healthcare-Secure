"use client";

import { usePatient } from "@/context/PatientContext";
import { formatIst } from "@/lib/datetimeIst";
import { patientInitials } from "@/lib/patientInitials";
import { useI18n } from "@/lib/i18n";

export default function PatientCardHeader() {
  const { t } = useI18n();
  const {
    patientName,
    patientPhone,
    clinicMrn,
    abhaNumber,
    patientAgeYears,
    locked,
  } = usePatient();

  if (!locked) return null;

  return (
    <header className="mb-4 flex gap-4 border-b border-slate-100 pb-4 dark:border-slate-800">
      <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-teal-100 text-xl font-bold text-teal-900 dark:bg-teal-900/50 dark:text-teal-100">
        {patientInitials(patientName)}
      </span>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-xl font-semibold text-slate-900 dark:text-slate-100">
          {patientName}
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {patientPhone ? `***${patientPhone.slice(-4)}` : "—"}
          {clinicMrn ? ` · MRN ${clinicMrn}` : ""}
        </p>
        {patientAgeYears ? (
          <p className="text-xs text-slate-500">
            {t("patientAge")}: {patientAgeYears}
          </p>
        ) : null}
        {abhaNumber ? (
          <p className="text-xs text-slate-500">ABHA: {abhaNumber}</p>
        ) : null}
      </div>
    </header>
  );
}
