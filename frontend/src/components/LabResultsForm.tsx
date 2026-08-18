"use client";

import { FormEvent, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { useI18n } from "@/lib/i18n";
import { apiFetch } from "@/lib/doctorSession";
import { enqueueOffline } from "@/lib/offlineQueue";

type Props = {
  suggestedTest?: string;
};

export default function LabResultsForm({ suggestedTest = "" }: Props) {
  const { locked, rawIdentifier, bumpHistory } = usePatient();
  const { t } = useI18n();
  const [testName, setTestName] = useState("");
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState("");
  const [refRange, setRefRange] = useState("");
  const [collectedAt, setCollectedAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (suggestedTest.trim()) {
      setTestName(suggestedTest.trim());
    }
  }, [suggestedTest]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!locked || !rawIdentifier.trim()) {
      setStatus("Select a patient first.");
      return;
    }
    if (!testName.trim() || !value.trim()) {
      setStatus("Enter test name and value.");
      return;
    }
    const payload = {
      raw_identifier: rawIdentifier.trim(),
      test_name: testName.trim(),
      value: value.trim(),
      unit: unit.trim(),
      reference_range: refRange.trim(),
      collected_at: collectedAt.trim(),
    };
    setBusy(true);
    setStatus(null);
    try {
      const response = await apiFetch("/api/v1/history/lab-results", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setStatus("Lab result saved.");
      setTestName("");
      setValue("");
      setUnit("");
      setRefRange("");
      bumpHistory();
    } catch {
      enqueueOffline("/api/v1/history/lab-results", payload);
      setStatus(t("offlineQueued"));
      setTestName("");
      setValue("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <CollapsibleSection
      hint="Structured values the doctor can read on the timeline without opening a PDF."
      title={t("labResults")}
    >
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={onSubmit}>
        <input
          className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 text-sm"
          disabled={!locked || busy}
          onChange={(e) => setTestName(e.target.value)}
          placeholder="Test name (e.g. HbA1c)"
          value={testName}
        />
        <input
          className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 text-sm"
          disabled={!locked || busy}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Value"
          value={value}
        />
        <input
          className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 text-sm"
          disabled={!locked || busy}
          onChange={(e) => setUnit(e.target.value)}
          placeholder="Unit"
          value={unit}
        />
        <input
          className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 text-sm"
          disabled={!locked || busy}
          onChange={(e) => setRefRange(e.target.value)}
          placeholder="Reference range"
          value={refRange}
        />
        <input
          className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 text-sm sm:col-span-2"
          disabled={!locked || busy}
          onChange={(e) => setCollectedAt(e.target.value)}
          placeholder="Collected date (optional)"
          value={collectedAt}
        />
        <button
          className="min-h-12 rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60 sm:col-span-2"
          disabled={!locked || busy}
          type="submit"
        >
          {busy ? "Saving…" : t("saveLab")}
        </button>
      </form>
      {status ? (
        <p className="mt-3 text-sm text-slate-700" role="status">
          {status}
        </p>
      ) : null}
    </CollapsibleSection>
  );
}
