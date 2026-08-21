"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import AppHeader from "@/components/home/AppHeader";
import { useNotifications } from "@/context/NotificationContext";
import { notifyAppointmentsChanged } from "@/hooks/useAppointments";
import { patientCardPath } from "@/lib/clinicRoutes";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

const INPUT =
  "mt-1 min-h-12 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm dark:border-slate-600 dark:bg-slate-900";

export default function NewPatientPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { push: pushNotification } = useNotifications();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [mrn, setMrn] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const displayName = name.trim();
      const digits = phone.replace(/\D+/g, "");
      const clinicMrn = mrn.trim();
      if (!displayName) throw new Error(t("nameRequired"));
      if (digits.length !== 10 && !clinicMrn) {
        throw new Error(t("mobileOrMrnRequired"));
      }
      const res = await apiFetch("/api/v1/history/tokenize", {
        method: "POST",
        body: JSON.stringify({
          patient_name: displayName,
          patient_phone: digits.length === 10 ? digits : undefined,
          clinic_mrn: clinicMrn || undefined,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { blind_patient_id?: string };
      if (!data.blind_patient_id) throw new Error(t("openPatientFailed"));
      notifyAppointmentsChanged();
      pushNotification({
        title: t("notifPatientAdded"),
        body: displayName,
        href: patientCardPath(data.blind_patient_id, "appointment"),
      });
      router.replace(patientCardPath(data.blind_patient_id, "appointment"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("openPatientFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pb-8">
      <AppHeader
        leading={
          <button
            aria-label="Back"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 text-slate-700"
            onClick={() => router.back()}
            type="button"
          >
            ←
          </button>
        }
        showMenu={false}
        title={t("createPatient")}
      />
      <form className="mt-4 space-y-4" onSubmit={onSave}>
        <label className="block text-xs font-medium text-slate-600">
          {t("name")}
          <input
            className={INPUT}
            onChange={(e) => setName(e.target.value)}
            required
            value={name}
          />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          {t("mobile")}
          <input
            className={INPUT}
            inputMode="numeric"
            onChange={(e) => setPhone(e.target.value)}
            value={phone}
          />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          {t("appointmentMrn")}
          <input
            className={INPUT}
            onChange={(e) => setMrn(e.target.value)}
            value={mrn}
          />
        </label>
        <button
          className="min-h-12 w-full rounded-lg bg-teal-600 text-sm font-medium text-white disabled:opacity-50"
          disabled={busy}
          type="submit"
        >
          {t("save")}
        </button>
      </form>
      {error ? (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
