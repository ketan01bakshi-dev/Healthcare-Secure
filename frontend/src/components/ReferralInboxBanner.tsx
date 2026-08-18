"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useActiveClinicRole } from "@/components/DoctorGate";
import { usePatient } from "@/context/PatientContext";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

type InboxItem = {
  id: string;
  blind_patient_id: string;
  created_at?: string | null;
  from_display_name?: string;
  patient_display_name?: string;
  clinic_mrn?: string;
  raw_identifier?: string;
  note?: string;
};

export default function ReferralInboxBanner() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const router = useRouter();
  const { lockFromHandoff } = usePatient();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (role !== "doctor") {
      setItems([]);
      return;
    }
    try {
      const res = await apiFetch("/api/v1/history/referrals/inbox");
      if (!res.ok) {
        setItems([]);
        return;
      }
      const data = (await res.json()) as InboxItem[];
      setItems(Array.isArray(data) ? data : []);
    } catch {
      setItems([]);
    }
  }, [role]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onOpen = useCallback(
    async (item: InboxItem) => {
      setBusyId(item.id);
      setError(null);
      try {
        await lockFromHandoff({
          displayName: item.patient_display_name || "Patient",
          clinicMrn: item.clinic_mrn,
          blindPatientId: item.blind_patient_id,
        });
        await apiFetch(`/api/v1/history/referral-handoff/${item.id}/ack`, {
          method: "POST",
        });
        setItems((prev) => prev.filter((x) => x.id !== item.id));
        router.push("/visit/");
      } catch (e) {
        setError(e instanceof Error ? e.message : t("referralOpenFailed"));
      } finally {
        setBusyId(null);
      }
    },
    [lockFromHandoff, router, t],
  );

  const onAck = useCallback(async (item: InboxItem) => {
    setBusyId(item.id);
    setError(null);
    try {
      await apiFetch(`/api/v1/history/referral-handoff/${item.id}/ack`, {
        method: "POST",
      });
      setItems((prev) => prev.filter((x) => x.id !== item.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("referralOpenFailed"));
    } finally {
      setBusyId(null);
    }
  }, [t]);

  if (role !== "doctor" || items.length === 0) {
    return null;
  }

  return (
    <section
      aria-label={t("referralInbox")}
      className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-900">
        {t("referralInbox")}
      </h2>
      <p className="mt-1 text-sm text-amber-950">{t("referralInboxHint")}</p>
      <ul className="mt-3 space-y-3">
        {items.map((item) => (
          <li
            key={item.id}
            className="rounded-lg border border-amber-100 bg-white px-3 py-3"
          >
            <p className="text-sm font-medium text-slate-900">
              {item.patient_display_name || "Patient"}
              {item.clinic_mrn ? (
                <span className="ml-2 text-xs font-normal text-slate-500">
                  MRN {item.clinic_mrn}
                </span>
              ) : null}
            </p>
            <p className="mt-0.5 text-xs text-slate-600">
              {t("referralFrom")}: {item.from_display_name || "—"}
            </p>
            {item.note ? (
              <p className="mt-1 text-sm text-slate-700">{item.note}</p>
            ) : null}
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                className="inline-flex min-h-10 items-center justify-center rounded-lg bg-slate-900 px-3 text-sm font-medium text-white disabled:opacity-50"
                disabled={busyId === item.id}
                onClick={() => void onOpen(item)}
                type="button"
              >
                {t("referralOpenPatient")}
              </button>
              <button
                className="inline-flex min-h-10 items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 disabled:opacity-50"
                disabled={busyId === item.id}
                onClick={() => void onAck(item)}
                type="button"
              >
                {t("referralAck")}
              </button>
            </div>
          </li>
        ))}
      </ul>
      {error ? (
        <p className="mt-2 text-sm text-amber-900" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
