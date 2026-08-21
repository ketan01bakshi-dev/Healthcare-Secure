"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import CollapsibleSection from "@/components/CollapsibleSection";
import { useActiveClinicRole } from "@/components/DoctorGate";
import { usePatient } from "@/context/PatientContext";
import {
  formatIstTime,
  isSameIstDay,
  istDayBoundsIso,
} from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";
import { pathAfterPatientLock } from "@/lib/clinicRoutes";

type AppointmentRow = {
  id: string;
  display_name: string;
  phone_last4: string;
  scheduled_at: string | null;
  reason: string;
  modality?: string;
  status: string;
  sms_status: string;
};

/** Waiting List — today's booked appointments (from Appointments block). */
export default function WaitingQueue() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const router = useRouter();
  const { lockFromAppointment } = usePatient();
  const [items, setItems] = useState<AppointmentRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const { from, to } = istDayBoundsIso();
      const res = await apiFetch(
        `/api/v1/appointments?status=booked&from_date=${encodeURIComponent(from)}&to_date=${encodeURIComponent(to)}`,
      );
      if (!res.ok) return;
      const data = (await res.json()) as AppointmentRow[];
      setItems(
        (Array.isArray(data) ? data : []).filter((r) =>
          isSameIstDay(r.scheduled_at),
        ),
      );
    } catch {
      /* offline */
    }
  }, []);

  useEffect(() => {
    if (role === "lab") return;
    void load();
    const id = window.setInterval(() => void load(), 30000);
    const onChange = () => void load();
    window.addEventListener("healthcare-appointments-changed", onChange);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("healthcare-appointments-changed", onChange);
    };
  }, [load, role]);

  if (role === "lab") return null;

  async function markDone(id: string) {
    setBusy(true);
    setStatus(null);
    try {
      const res = await apiFetch(`/api/v1/appointments/${id}/done`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus(t("markedDone"));
      await load();
      window.dispatchEvent(new Event("healthcare-appointments-changed"));
    } catch {
      setStatus(t("markDoneFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function openPatient(item: AppointmentRow) {
    setBusy(true);
    setStatus(null);
    try {
      const blindId = await lockFromAppointment(item.id);
      setStatus(t("patientOpened"));
      router.push(pathAfterPatientLock(role, blindId));
    } catch {
      setStatus(t("openPatientFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CollapsibleSection hint={t("waitingListHint")} title={t("waitingList")}>
      {status ? (
        <p className="text-sm text-slate-600" role="status">
          {status}
        </p>
      ) : null}
      <ul className="divide-y divide-slate-100">
        {items.length === 0 ? (
          <li className="py-3 text-sm text-slate-500">{t("noOneWaiting")}</li>
        ) : (
          items.map((item, index) => (
            <li
              className="flex items-center justify-between gap-3 py-3"
              key={item.id}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900">
                  {index + 1}. {item.display_name}
                  {(item.modality || "").toLowerCase() === "video" ? (
                    <span className="ml-2 inline-flex rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-900">
                      {t("videoBadge")}
                    </span>
                  ) : null}
                </p>
                <p className="text-xs text-slate-500">
                  {item.scheduled_at
                    ? formatIstTime(item.scheduled_at)
                    : "—"}
                  {item.reason ? ` · ${item.reason}` : ""}
                  {item.phone_last4 ? ` · ***${item.phone_last4}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  className="min-h-10 rounded-lg bg-slate-900 px-3 text-xs font-medium text-white disabled:opacity-50"
                  disabled={busy}
                  onClick={() => void openPatient(item)}
                  type="button"
                >
                  {t("openPatient")}
                </button>
                <button
                  className="min-h-10 rounded-lg border border-slate-200 px-3 text-xs text-slate-800 disabled:opacity-50"
                  disabled={busy}
                  onClick={() => void markDone(item.id)}
                  type="button"
                >
                  {t("done")}
                </button>
              </div>
            </li>
          ))
        )}
      </ul>
    </CollapsibleSection>
  );
}
