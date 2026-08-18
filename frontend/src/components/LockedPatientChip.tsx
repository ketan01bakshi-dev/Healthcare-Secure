"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { usePatient } from "@/context/PatientContext";
import { useClinicFeatures } from "@/components/DoctorGate";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";
import {
  gestationalAgeAt,
  gplaLabel,
  type ObstetricProfile,
} from "@/lib/obstetric";

/** Sticky chip so every tab shows who is locked without scrolling to Patient. */
export default function LockedPatientChip() {
  const { t } = useI18n();
  const { has } = useClinicFeatures();
  const obstetricEnabled = has("obstetric");
  const {
    locked,
    patientName,
    patientPhone,
    clinicMrn,
    rawIdentifier,
    historyVersion,
  } = usePatient();
  const [obs, setObs] = useState<ObstetricProfile | null>(null);

  useEffect(() => {
    if (!obstetricEnabled || !locked || !rawIdentifier) {
      setObs(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch(
          `/api/v1/history/obstetric-profile?raw_identifier=${encodeURIComponent(rawIdentifier)}`,
        );
        if (!res.ok || cancelled) return;
        const text = await res.text();
        if (!text || text === "null") {
          if (!cancelled) setObs(null);
          return;
        }
        if (!cancelled) setObs(JSON.parse(text) as ObstetricProfile);
      } catch {
        if (!cancelled) setObs(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [obstetricEnabled, locked, rawIdentifier, historyVersion]);

  if (!locked) {
    return (
      <div className="mb-4 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3">
        <p className="text-sm text-slate-600">{t("noPatientLocked")}</p>
        <Link
          href="/today/#all-patients"
          className="mt-2 inline-flex min-h-10 items-center text-sm font-medium text-slate-900 underline"
        >
          {t("selectPatient")}
        </Link>
      </div>
    );
  }

  const detail = clinicMrn
    ? `MRN ${clinicMrn}`
    : patientPhone
      ? patientPhone
      : "";
  const ga = obs ? gestationalAgeAt(obs.lmp) : null;

  return (
    <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          {t("activePatient")}
        </p>
        <p className="truncate text-sm font-semibold text-slate-900">
          {patientName || t("patient")}
        </p>
        {detail ? (
          <p className="truncate text-xs text-slate-500">{detail}</p>
        ) : null}
        {obstetricEnabled && ga ? (
          <p className="truncate text-xs font-medium text-teal-800">
            {ga.label}
            {obs ? ` · ${gplaLabel(obs)}` : ""}
            {obs?.edd ? ` · EDD ${obs.edd}` : ""}
          </p>
        ) : null}
      </div>
      <Link
        href="/today/#all-patients"
        className="shrink-0 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-800"
      >
        {t("changePatient")}
      </Link>
    </div>
  );
}
