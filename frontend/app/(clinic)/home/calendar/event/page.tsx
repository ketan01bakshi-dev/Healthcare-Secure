"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useActiveClinicRole } from "@/components/DoctorGate";
import AppHeader from "@/components/home/AppHeader";
import BurgerDrawer from "@/components/home/BurgerDrawer";
import type { AppointmentRow } from "@/lib/appointmentGroups";
import { formatIst, formatIstTime } from "@/lib/datetimeIst";
import { pathAfterPatientLock } from "@/lib/clinicRoutes";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";
import { patientInitials } from "@/lib/patientInitials";
import { usePatient } from "@/context/PatientContext";
import { notifyAppointmentsChanged } from "@/hooks/useAppointments";

export default function AppointmentEventPage() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = searchParams.get("id");
  const role = useActiveClinicRole();
  const { lockFromAppointment } = usePatient();
  const [item, setItem] = useState<AppointmentRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      const res = await apiFetch("/api/v1/appointments?status=booked");
      if (!res.ok) return;
      const rows = (await res.json()) as AppointmentRow[];
      setItem(rows.find((r) => r.id === id) || null);
    })();
  }, [id]);

  const openPatient = async () => {
    if (!item) return;
    setBusy(true);
    try {
      const blindId = await lockFromAppointment(item.id);
      router.push(pathAfterPatientLock(role, blindId));
    } catch {
      setStatus(t("openPatientFailed"));
    } finally {
      setBusy(false);
    }
  };

  async function markDone() {
    if (!item) return;
    setBusy(true);
    try {
      const res = await apiFetch(`/api/v1/appointments/${item.id}/done`, {
        method: "POST",
      });
      if (!res.ok) throw new Error();
      notifyAppointmentsChanged();
      router.back();
    } catch {
      setStatus(t("markDoneFailed"));
    } finally {
      setBusy(false);
    }
  }

  if (!item) {
    return (
      <div className="p-4">
        <p className="text-sm text-slate-500">{t("loadingAppointments")}</p>
      </div>
    );
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
        onMenuClick={() => setMenuOpen(true)}
        title={t("appointmentDetails")}
      />
      <div className="mt-4 flex gap-4">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-100 text-lg font-bold text-teal-900">
          {patientInitials(item.display_name)}
        </span>
        <div>
          <h2 className="text-lg font-semibold">{item.display_name}</h2>
          <p className="text-sm text-slate-600">
            {item.scheduled_at
              ? `${formatIst(item.scheduled_at)}`
              : "—"}
          </p>
        </div>
      </div>
      <section className="mt-6 space-y-2">
        <h3 className="text-sm font-semibold text-slate-800">≡ {t("details")}</h3>
        <p className="text-sm text-slate-600">
          {t("appointmentWhen")}:{" "}
          {item.scheduled_at ? formatIstTime(item.scheduled_at) : "—"}
        </p>
        {item.reason ? (
          <p className="text-sm text-slate-600">
            {t("appointmentReason")}: {item.reason}
          </p>
        ) : null}
        {item.phone_last4 ? (
          <p className="text-sm text-slate-600">***{item.phone_last4}</p>
        ) : null}
      </section>
      <div className="mt-6 flex flex-wrap gap-2">
        <button
          className="min-h-12 rounded-lg bg-slate-900 px-4 text-sm font-medium text-white disabled:opacity-50"
          disabled={busy}
          onClick={() => void openPatient()}
          type="button"
        >
          {t("openPatient")}
        </button>
        <button
          className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm disabled:opacity-50"
          disabled={busy}
          onClick={() => void markDone()}
          type="button"
        >
          {t("done")}
        </button>
      </div>
      {status ? (
        <p className="mt-2 text-sm text-slate-600" role="status">
          {status}
        </p>
      ) : null}
      <BurgerDrawer onClose={() => setMenuOpen(false)} open={menuOpen} />
    </div>
  );
}
