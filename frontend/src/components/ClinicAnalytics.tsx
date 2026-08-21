"use client";

import { useCallback, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { useActiveClinicRole } from "@/components/DoctorGate";
import { apiFetch } from "@/lib/doctorSession";
import { shareOrDownloadBlob } from "@/lib/fileActions";
import { useI18n } from "@/lib/i18n";

type FrequencyItem = { name: string; count: number };

type PeriodBilling = {
  total_inr: number;
  billed_patients: number;
  per_patient_inr: number;
  bill_count: number;
};

type PeriodOverview = {
  key: string;
  label: string;
  start_date: string;
  end_date: string;
  patients_visited: number;
  encounters: number;
  medications: FrequencyItem[];
  diagnoses: FrequencyItem[];
  billing: PeriodBilling;
};

type ClinicOverview = {
  periods: PeriodOverview[];
};

type SttMemoryMetrics = {
  feedback_count: number;
  rx_with_med_name_edits: number;
  med_name_edit_rate: number;
  top_correction_pairs: { from: string; to: string; count: number }[];
  top_aliases: {
    from: string;
    to: string;
    kind: string;
    hit_count: number;
  }[];
  glossary_term_count: number;
};

type TodaySummary = {
  lab_results_today: number;
};

type PeriodKey = "today" | "week" | "year";

function formatInr(amount: number): string {
  return `₹${amount.toLocaleString("en-IN", {
    minimumFractionDigits: amount % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function ClinicAnalytics() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const [overview, setOverview] = useState<ClinicOverview | null>(null);
  const [sttMemory, setSttMemory] = useState<SttMemoryMetrics | null>(null);
  const [todayLab, setTodayLab] = useState<TodaySummary | null>(null);
  const [period, setPeriod] = useState<PeriodKey>("today");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setError(null);
    let loaded = true;
    try {
      const todayRes = await apiFetch("/api/v1/analytics/today");
      if (!todayRes.ok) throw new Error(await todayRes.text());
      setTodayLab((await todayRes.json()) as TodaySummary);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("analyticsLoadError"));
      setTodayLab(null);
      loaded = false;
    }
    if (role === "lab") return loaded;
    try {
      const [res, sttRes] = await Promise.all([
        apiFetch("/api/v1/analytics/overview?limit=10"),
        apiFetch("/api/v1/analytics/stt-memory"),
      ]);
      if (!res.ok) throw new Error(await res.text());
      setOverview((await res.json()) as ClinicOverview);
      if (sttRes.ok) {
        setSttMemory((await sttRes.json()) as SttMemoryMetrics);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("analyticsLoadError"));
      setOverview(null);
      loaded = false;
    }
    return loaded;
  }, [role, t]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    setNotice(null);
    try {
      const loaded = await loadAll();
      if (loaded) setNotice(t("analyticsRefreshed"));
    } finally {
      setRefreshing(false);
    }
  }, [loadAll, t]);

  const onExport = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/analytics/export.csv?days=30");
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const action = await shareOrDownloadBlob(blob, "clinic_export_30d.csv");
      setNotice(
        action === "shared" ? t("exportShareOpened") : t("exportDownloaded"),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("exportFailed"));
    } finally {
      setBusy(false);
    }
  }, [t]);

  if (role === "lab") {
    return (
      <CollapsibleSection title={t("analytics")}>
        <p className="text-sm text-slate-600">
          {t("labResultsToday")}:{" "}
          <span className="font-medium text-slate-900">
            {todayLab?.lab_results_today ?? "—"}
          </span>
        </p>
      </CollapsibleSection>
    );
  }

  const active =
    overview?.periods.find((p) => p.key === period) ?? overview?.periods[0] ?? null;

  const periodTabs: { key: PeriodKey; label: string }[] = [
    { key: "today", label: t("analyticsPeriodToday") },
    { key: "week", label: t("analyticsPeriodWeek") },
    { key: "year", label: t("analyticsPeriodYear") },
  ];

  return (
    <CollapsibleSection
      className="space-y-4 rounded-xl border border-slate-200 bg-white px-4 py-4"
      headerActions={
        <div className="flex gap-2">
          <button
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-800"
            disabled={refreshing}
            onClick={() => void onRefresh()}
            type="button"
          >
            {refreshing ? t("refreshing") : t("refresh")}
          </button>
          {role === "doctor" ? (
            <button
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-800"
              disabled={busy}
              onClick={() => void onExport()}
              type="button"
            >
              {t("exportCsv")}
            </button>
          ) : null}
        </div>
      }
      title={t("analytics")}
    >
      {error ? <p className="text-sm text-amber-800">{error}</p> : null}
      {notice ? (
        <p className="text-sm text-emerald-800" role="status">
          {notice}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {periodTabs.map((tab) => (
          <button
            key={tab.key}
            className={
              period === tab.key
                ? "rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
                : "rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-700"
            }
            onClick={() => setPeriod(tab.key)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      {!active ? (
        <p className="text-sm text-slate-500">{t("loadingSummary")}</p>
      ) : (
        <>
          <p className="text-xs text-slate-500">
            {active.start_date}
            {active.start_date !== active.end_date ? ` → ${active.end_date}` : ""}
          </p>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat label={t("patientsVisited")} value={active.patients_visited} />
            <Stat label={t("encounters")} value={active.encounters} />
            <Stat
              label={t("totalBilling")}
              value={formatInr(active.billing.total_inr)}
            />
            <Stat
              label={t("perPatientBilling")}
              value={formatInr(active.billing.per_patient_inr)}
            />
            <Stat label={t("billedPatients")} value={active.billing.billed_patients} />
            <Stat label={t("billsRecorded")} value={active.billing.bill_count} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <FreqList title={t("topMedications")} items={active.medications} />
            <FreqList title={t("topDiagnoses")} items={active.diagnoses} />
          </div>
        </>
      )}

      {sttMemory ? (
        <div className="space-y-2 border-t border-slate-100 pt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {t("sttMemoryTitle")}
          </h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat
              label={t("sttFeedbackCount")}
              value={sttMemory.feedback_count}
            />
            <Stat
              label={t("sttMedEditRate")}
              value={`${Math.round(sttMemory.med_name_edit_rate * 100)}%`}
            />
            <Stat
              label={t("sttGlossaryTerms")}
              value={sttMemory.glossary_term_count}
            />
          </div>
          {sttMemory.top_correction_pairs.length > 0 ? (
            <FreqList
              title={t("sttTopCorrections")}
              items={sttMemory.top_correction_pairs.map((p) => ({
                name: `${p.from} → ${p.to}`,
                count: p.count,
              }))}
            />
          ) : (
            <p className="text-sm text-slate-500">{t("sttNoCorrectionsYet")}</p>
          )}
        </div>
      ) : null}
    </CollapsibleSection>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function FreqList({
  title,
  items,
}: {
  title: string;
  items: FrequencyItem[];
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">—</p>
      ) : (
        <ul className="mt-2 max-h-36 space-y-1 overflow-y-auto text-sm text-slate-800">
          {items.map((it) => (
            <li key={it.name} className="flex justify-between gap-2">
              <span className="truncate">{it.name}</span>
              <span className="shrink-0 text-slate-500">{it.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
