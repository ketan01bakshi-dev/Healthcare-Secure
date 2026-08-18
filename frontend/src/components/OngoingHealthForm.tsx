"use client";

import { FormEvent, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

const INPUT =
  "mt-1 min-h-24 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-slate-400 focus:ring-2";

/** Patient-level ongoing medications and chronic health issues. */
export default function OngoingHealthForm() {
  const { t } = useI18n();
  const { locked, rawIdentifier, bumpHistory, historyVersion } = usePatient();
  const [medications, setMedications] = useState("");
  const [issues, setIssues] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!locked || !rawIdentifier) {
      setMedications("");
      setIssues("");
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch(
          `/api/v1/history/health-profile?raw_identifier=${encodeURIComponent(rawIdentifier)}`,
        );
        if (!res.ok || cancelled) return;
        const text = await res.text();
        if (!text || text === "null") {
          if (!cancelled) {
            setMedications("");
            setIssues("");
          }
          return;
        }
        const data = JSON.parse(text) as {
          ongoing_medications?: string;
          health_issues?: string;
        };
        if (cancelled) return;
        setMedications(data.ongoing_medications || "");
        setIssues(data.health_issues || "");
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locked, rawIdentifier, historyVersion]);

  if (!locked) return null;

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!rawIdentifier) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const res = await apiFetch("/api/v1/history/health-profile", {
        method: "PUT",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          ongoing_medications: medications,
          health_issues: issues,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as {
        ongoing_medications?: string;
        health_issues?: string;
      };
      setMedications(data.ongoing_medications || "");
      setIssues(data.health_issues || "");
      setStatus(t("healthProfileSaved"));
      bumpHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("healthProfileSaveFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CollapsibleSection
      hint={t("healthProfileHint")}
      title={t("healthProfile")}
    >
      <form className="grid gap-3" onSubmit={onSave}>
        <label className="block text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("ongoingMedications")}
          <textarea
            className={INPUT}
            disabled={busy}
            maxLength={2000}
            onChange={(e) => setMedications(e.target.value)}
            placeholder={t("ongoingMedicationsPlaceholder")}
            value={medications}
          />
        </label>
        <label className="block text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("healthIssues")}
          <textarea
            className={INPUT}
            disabled={busy}
            maxLength={2000}
            onChange={(e) => setIssues(e.target.value)}
            placeholder={t("healthIssuesPlaceholder")}
            value={issues}
          />
        </label>
        <button
          className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60"
          disabled={busy}
          type="submit"
        >
          {busy ? "Saving…" : t("saveHealthProfile")}
        </button>
      </form>
      {error ? (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
      {status ? (
        <p className="mt-2 text-sm text-emerald-800" role="status">
          {status}
        </p>
      ) : null}
    </CollapsibleSection>
  );
}
