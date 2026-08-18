"use client";

import { useCallback, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { formatIst } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";
import { gplaLabel, type ObstetricProfile } from "@/lib/obstetric";

type AlertRow = { code: string; severity: string; message: string };

type TrendField = {
  latest?: number | string | null;
  previous?: number | string | null;
  delta?: number | null;
  delta_diastolic?: number | null;
  direction?: string;
} | null;

type VitalsPoint = {
  at?: string | null;
  systolic?: string | null;
  diastolic?: string | null;
  weight?: string | null;
  hemoglobin?: string | null;
  pulse?: string | null;
  source?: string;
};

type DoctorComment = {
  at?: string | null;
  text: string;
  source?: string;
  entered_by?: string | null;
};

type CaseSummary = {
  gestational_age?: string | null;
  obstetric?: ObstetricProfile | null;
  narrative?: string | null;
  vitals_latest?: {
    bp?: TrendField;
    weight?: TrendField;
    hemoglobin?: TrendField;
    pulse?: TrendField;
  };
  vitals_trends?: {
    bp_diastolic?: TrendField;
    weight?: TrendField;
    hemoglobin?: TrendField;
    pulse?: TrendField;
  };
  vitals_points?: VitalsPoint[];
  labs_recent?: {
    test_name: string;
    value: string;
    unit: string;
    at?: string;
  }[];
  documents_recent?: {
    id: string;
    title: string;
    document_kind: string;
    findings?: { summary?: string } | null;
    findings_summary?: string | null;
    at?: string;
  }[];
  doctor_comments?: DoctorComment[];
  alerts?: AlertRow[];
  scan_cadence?: {
    code: string;
    label: string;
    status: string;
    window_weeks: string;
    matched_document?: boolean;
  }[];
  next_appointment?: { scheduled_at?: string; reason?: string } | null;
  last_prescription?: {
    diagnoses?: string[];
    at?: string;
  } | null;
  disclaimer?: string;
};

type ConsultPack = {
  concerns?: string[];
  questions_to_ask?: string[];
  suggested_workup?: string[];
  rx_checklist?: string[];
  summary?: string;
  llm_used?: boolean;
  disclaimer?: string;
};

function severityClass(s: string) {
  if (s === "critical") return "border-red-300 bg-red-50 text-red-900";
  if (s === "warn") return "border-amber-300 bg-amber-50 text-amber-950";
  return "border-slate-200 bg-slate-50 text-slate-800";
}

function cadenceClass(status: string) {
  if (status === "due") return "text-amber-800";
  if (status === "documented") return "text-emerald-800";
  if (status === "past_window") return "text-slate-500";
  return "text-slate-700";
}

function formatPoint(p: VitalsPoint): string {
  const bits: string[] = [];
  if (p.systolic && p.diastolic) bits.push(`BP ${p.systolic}/${p.diastolic}`);
  if (p.weight) bits.push(`Wt ${p.weight}`);
  if (p.hemoglobin) bits.push(`Hb ${p.hemoglobin}`);
  if (p.pulse) bits.push(`Pulse ${p.pulse}`);
  return bits.join(" · ") || "—";
}

function trendLabel(direction?: string | null): string {
  if (direction === "rising" || direction === "falling" || direction === "stable") {
    return direction;
  }
  return "";
}

/** Consolidated decision-support brief for the locked patient. */
export default function PatientCaseBrief() {
  const { t } = useI18n();
  const { locked, rawIdentifier, historyVersion } = usePatient();
  const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [pack, setPack] = useState<ConsultPack | null>(null);
  const [busy, setBusy] = useState(false);
  const [packBusy, setPackBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!locked || !rawIdentifier) {
      setSummary(null);
      setPack(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch(
        `/api/v1/history/case-summary?raw_identifier=${encodeURIComponent(rawIdentifier)}`,
      );
      if (!res.ok) throw new Error(await res.text());
      setSummary((await res.json()) as CaseSummary);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("caseBriefFailed"));
      setSummary(null);
    } finally {
      setBusy(false);
    }
  }, [locked, rawIdentifier, t]);

  useEffect(() => {
    void load();
  }, [load, historyVersion]);

  async function onConsultPack() {
    if (!rawIdentifier) return;
    setPackBusy(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/history/consult-pack", {
        method: "POST",
        body: JSON.stringify({ raw_identifier: rawIdentifier }),
      });
      if (!res.ok) throw new Error(await res.text());
      setPack((await res.json()) as ConsultPack);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("consultPackFailed"));
    } finally {
      setPackBusy(false);
    }
  }

  if (!locked) return null;

  const obs = summary?.obstetric;
  const vl = summary?.vitals_latest;
  const trends = summary?.vitals_trends;
  const points = [...(summary?.vitals_points || [])].reverse().slice(0, 8);
  const comments = summary?.doctor_comments || [];

  return (
    <CollapsibleSection
      headerActions={
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-800"
            disabled={busy}
            onClick={() => void load()}
          >
            {t("refresh")}
          </button>
          <button
            type="button"
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            disabled={packBusy || !summary}
            onClick={() => void onConsultPack()}
          >
            {packBusy ? t("consultPackLoading") : t("consultPack")}
          </button>
        </div>
      }
      hint={t("caseBriefHint")}
      title={t("caseBrief")}
    >
      {error ? (
        <p className="text-sm text-amber-800" role="alert">
          {error}
        </p>
      ) : null}
      {busy && !summary ? (
        <p className="text-sm text-slate-500">{t("loadingSummary")}</p>
      ) : null}

      {summary ? (
        <>
          {summary.narrative ? (
            <p className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
              {summary.narrative}
            </p>
          ) : null}

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
              <p className="text-[10px] font-semibold uppercase text-slate-500">
                {t("gestationalAge")}
              </p>
              <p className="font-medium text-slate-900">
                {summary.gestational_age || "—"}
                {obs ? ` · ${gplaLabel(obs)}` : ""}
              </p>
              {obs?.edd ? (
                <p className="text-xs text-slate-600">EDD {obs.edd}</p>
              ) : null}
              {obs?.high_risk_notes ? (
                <p className="mt-1 text-xs text-amber-900">
                  {obs.high_risk_notes}
                </p>
              ) : null}
            </div>
            <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
              <p className="text-[10px] font-semibold uppercase text-slate-500">
                {t("latestVitals")}
              </p>
              <p className="text-slate-800">
                BP {vl?.bp?.latest || "—"}
                {vl?.bp?.delta_diastolic != null
                  ? ` (Δ dia ${vl.bp.delta_diastolic > 0 ? "+" : ""}${vl.bp.delta_diastolic})`
                  : ""}
                {trendLabel(trends?.bp_diastolic?.direction)
                  ? ` · ${trendLabel(trends?.bp_diastolic?.direction)}`
                  : ""}
              </p>
              <p className="text-slate-800">
                Wt{" "}
                {vl?.weight?.latest != null ? `${vl.weight.latest} kg` : "—"}
                {vl?.weight?.delta != null
                  ? ` (Δ ${vl.weight.delta > 0 ? "+" : ""}${Number(vl.weight.delta).toFixed(1)})`
                  : ""}
                {trendLabel(trends?.weight?.direction)
                  ? ` · ${trendLabel(trends?.weight?.direction)}`
                  : ""}
              </p>
              <p className="text-slate-800">
                Hb{" "}
                {vl?.hemoglobin?.latest != null
                  ? `${vl.hemoglobin.latest} g/dL`
                  : "—"}
                {vl?.hemoglobin?.delta != null
                  ? ` (Δ ${vl.hemoglobin.delta > 0 ? "+" : ""}${Number(vl.hemoglobin.delta).toFixed(1)})`
                  : ""}
                {trendLabel(trends?.hemoglobin?.direction)
                  ? ` · ${trendLabel(trends?.hemoglobin?.direction)}`
                  : ""}
              </p>
              {vl?.pulse?.latest != null ? (
                <p className="text-slate-800">Pulse {vl.pulse.latest}</p>
              ) : null}
            </div>
          </div>

          {(summary.alerts || []).length > 0 ? (
            <ul className="space-y-1">
              {(summary.alerts || []).map((a) => (
                <li
                  key={a.code + a.message}
                  className={`rounded-lg border px-3 py-2 text-xs ${severityClass(a.severity)}`}
                >
                  {a.message}
                </li>
              ))}
            </ul>
          ) : null}

          {points.length > 0 ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t("vitalTrends")}
              </h3>
              <ul className="mt-1 space-y-0.5 text-xs text-slate-700">
                {points.map((p, i) => (
                  <li key={`${p.at || "p"}-${i}`}>
                    {p.at ? formatIst(p.at) : "—"}
                    {" · "}
                    {formatPoint(p)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {comments.length > 0 ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t("doctorComments")}
              </h3>
              <ul className="mt-1 space-y-1 text-xs text-slate-700">
                {comments.map((c, i) => (
                  <li key={`${c.at || "c"}-${i}`}>
                    {c.at ? (
                      <span className="text-slate-500">
                        {formatIst(c.at)}
                        {c.entered_by ? ` · ${c.entered_by}` : ""}
                        {" — "}
                      </span>
                    ) : null}
                    {c.text}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {(summary.scan_cadence || []).length > 0 ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t("scanCadence")}
              </h3>
              <ul className="mt-1 space-y-1 text-xs">
                {(summary.scan_cadence || []).map((c) => (
                  <li key={c.code} className={cadenceClass(c.status)}>
                    {c.label} ({c.window_weeks}w) — {c.status}
                    {c.matched_document ? " ✓" : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {(summary.labs_recent || []).length > 0 ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t("recentLabs")}
              </h3>
              <ul className="mt-1 space-y-0.5 text-xs text-slate-700">
                {(summary.labs_recent || []).slice(0, 5).map((lab, i) => (
                  <li key={`${lab.test_name}-${i}`}>
                    {lab.test_name}: {lab.value}
                    {lab.unit ? ` ${lab.unit}` : ""}
                    {lab.at ? ` · ${formatIst(lab.at)}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {(summary.documents_recent || []).length > 0 ? (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t("recentDocuments")}
              </h3>
              <ul className="mt-1 space-y-1 text-xs text-slate-700">
                {(summary.documents_recent || []).map((d) => (
                  <li key={d.id}>
                    {d.title}
                    {d.findings_summary || d.findings?.summary ? (
                      <span className="block text-slate-500">
                        {d.findings_summary || d.findings?.summary}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {summary.next_appointment?.scheduled_at ? (
            <p className="text-xs text-slate-600">
              {t("nextAppointment")}:{" "}
              {formatIst(summary.next_appointment.scheduled_at)}
              {summary.next_appointment.reason
                ? ` · ${summary.next_appointment.reason}`
                : ""}
            </p>
          ) : null}

          {summary.last_prescription?.diagnoses?.length ? (
            <p className="text-xs text-slate-600">
              {t("lastDiagnoses")}:{" "}
              {(summary.last_prescription.diagnoses || [])
                .map((d) => (typeof d === "string" ? d : String(d)))
                .join("; ")}
            </p>
          ) : null}
        </>
      ) : null}

      {pack ? (
        <div className="rounded-lg border border-teal-200 bg-teal-50/60 px-3 py-3 text-sm text-teal-950">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-teal-800">
            {t("consultPack")}
            {pack.llm_used === false ? ` (${t("ruleBased")})` : ""}
          </h3>
          {pack.summary ? <p className="mt-1">{pack.summary}</p> : null}
          <PackList title={t("concerns")} items={pack.concerns} />
          <PackList title={t("questionsToAsk")} items={pack.questions_to_ask} />
          <PackList title={t("suggestedWorkup")} items={pack.suggested_workup} />
          <PackList title={t("rxChecklist")} items={pack.rx_checklist} />
        </div>
      ) : null}

      <p className="text-[10px] text-slate-400">
        {summary?.disclaimer || t("decisionSupportDisclaimer")}
      </p>
    </CollapsibleSection>
  );
}

function PackList({
  title,
  items,
}: {
  title: string;
  items?: string[];
}) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mt-2">
      <p className="text-[10px] font-semibold uppercase text-teal-800">{title}</p>
      <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-xs">
        {items.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
