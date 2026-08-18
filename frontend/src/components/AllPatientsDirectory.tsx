"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import CollapsibleSection from "@/components/CollapsibleSection";
import { useActiveClinicRole } from "@/components/DoctorGate";
import { usePatient } from "@/context/PatientContext";
import { pathAfterPatientLock } from "@/lib/clinicRoutes";
import { formatIst } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

type PatientRow = {
  blind_patient_id: string;
  display_name: string;
  phone_last4: string;
  clinic_mrn: string;
  visit_count: number;
  last_seen_at: string | null;
  has_phone: boolean;
};

type PeriodFilter = "all" | "week" | "month";

/** All patients known to this clinic — search + period filters. */
export default function AllPatientsDirectory() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const router = useRouter();
  const { lockFromDirectory } = usePatient();
  const [items, setItems] = useState<PatientRow[]>([]);
  const [query, setQuery] = useState("");
  const [period, setPeriod] = useState<PeriodFilter>("all");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [openFromHash, setOpenFromHash] = useState(false);

  useEffect(() => {
    const applyHash = () => {
      if (window.location.hash !== "#all-patients") return;
      setOpenFromHash(true);
      window.requestAnimationFrame(() => {
        document
          .getElementById("all-patients")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    };
    applyHash();
    window.addEventListener("hashchange", applyHash);
    return () => window.removeEventListener("hashchange", applyHash);
  }, []);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (period !== "all") params.set("period", period);
      const qs = params.toString();
      const res = await apiFetch(
        `/api/v1/history/patients${qs ? `?${qs}` : ""}`,
      );
      if (!res.ok) {
        setStatus(t("allPatientsLoadFailed"));
        return;
      }
      const data = (await res.json()) as PatientRow[];
      setItems(Array.isArray(data) ? data : []);
      setStatus(null);
    } catch {
      setStatus(t("allPatientsLoadFailed"));
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  }, [period, query, t]);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 200);
    return () => window.clearTimeout(id);
  }, [load]);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void load({ silent: true });
    }, 15000);
    return () => window.clearInterval(id);
  }, [load]);

  async function openPatient(blindId: string) {
    setBusy(true);
    setStatus(null);
    try {
      await lockFromDirectory(blindId);
      setStatus(t("patientOpened"));
      router.push(pathAfterPatientLock(role));
    } catch (err) {
      setStatus(
        err instanceof Error ? err.message : t("openPatientFailed"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div id="all-patients">
      <CollapsibleSection
        defaultOpen={openFromHash}
        hint={t("allPatientsHint")}
        key={openFromHash ? "all-patients-open" : "all-patients"}
        title={t("allPatients")}
      >
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="block min-w-0 flex-1 text-xs font-medium text-slate-600">
          {t("searchPatients")}
          <input
            className="mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none ring-slate-400 focus:ring-2"
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPatientsPlaceholder")}
            value={query}
          />
        </label>
        <label className="block text-xs font-medium text-slate-600 sm:w-44">
          {t("filterPeriod")}
          <select
            className="mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900"
            onChange={(e) => setPeriod(e.target.value as PeriodFilter)}
            value={period}
          >
            <option value="all">{t("periodAll")}</option>
            <option value="week">{t("periodWeek")}</option>
            <option value="month">{t("periodMonth")}</option>
          </select>
        </label>
      </div>

      {status ? (
        <p className="text-sm text-slate-600" role="status">
          {status}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-slate-500">{t("loadingPatients")}</p>
      ) : null}

      <ul className="divide-y divide-slate-100">
        {!loading && items.length === 0 ? (
          <li className="py-3 text-sm text-slate-500">{t("noPatientsYet")}</li>
        ) : (
          items.map((item) => (
            <li
              className="flex items-center justify-between gap-3 py-3"
              key={item.blind_patient_id}
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">
                  {item.display_name}
                </p>
                <p className="text-xs text-slate-500">
                  {item.phone_last4 ? `***${item.phone_last4}` : "—"}
                  {item.clinic_mrn ? ` · MRN ${item.clinic_mrn}` : ""}
                  {` · ${item.visit_count} visit${item.visit_count === 1 ? "" : "s"}`}
                  {item.last_seen_at
                    ? ` · ${formatIst(item.last_seen_at)}`
                    : ""}
                </p>
              </div>
              <button
                className="shrink-0 rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                disabled={busy || (!item.has_phone && !item.clinic_mrn)}
                onClick={() => void openPatient(item.blind_patient_id)}
                title={
                  item.has_phone || item.clinic_mrn
                    ? undefined
                    : t("noPhoneStored")
                }
                type="button"
              >
                {t("openPatient")}
              </button>
            </li>
          ))
        )}
      </ul>
    </CollapsibleSection>
    </div>
  );
}
