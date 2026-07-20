"use client";

import { FormEvent, useState } from "react";

import { apiFetch, getClinicUser } from "@/lib/doctorSession";
import { usePatient } from "@/context/PatientContext";

const EMPTY = {
  blood_pressure: "",
  pulse: "",
  temperature: "",
  spo2: "",
  weight: "",
  height: "",
  respiratory_rate: "",
};

export default function VitalsForm() {
  const { locked, rawIdentifier, bumpHistory } = usePatient();
  const [vitals, setVitals] = useState(EMPTY);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!locked || !rawIdentifier.trim()) {
      setStatus("Select a patient first.");
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const response = await apiFetch("/api/v1/history/vitals", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier.trim(),
          vitals,
          diagnostic_notes: notes.trim(),
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Save failed (${response.status})`);
      }
      const user = getClinicUser();
      setStatus(
        `Saved${user ? ` as ${user.display_name}` : ""}. Visible on the timeline with your name.`,
      );
      setVitals(EMPTY);
      setNotes("");
      bumpHistory();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  const fields: { key: keyof typeof EMPTY; label: string }[] = [
    { key: "blood_pressure", label: "Blood pressure" },
    { key: "pulse", label: "Pulse" },
    { key: "temperature", label: "Temperature" },
    { key: "spo2", label: "SpO₂" },
    { key: "weight", label: "Weight" },
    { key: "height", label: "Height" },
    { key: "respiratory_rate", label: "Respiratory rate" },
  ];

  return (
    <section
      aria-label="Vitals and diagnostics"
      className="mx-auto w-full max-w-3xl rounded-2xl border border-slate-200 bg-white px-4 py-6 shadow-sm sm:px-6"
    >
      <h2 className="text-lg font-semibold text-slate-900">
        Vitals & notes
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        Blood pressure, pulse, and other readings for this visit.
      </p>

      <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={onSubmit}>
        {fields.map((field) => (
          <label
            className="block text-xs uppercase tracking-wide text-slate-500"
            key={field.key}
          >
            {field.label}
            <input
              className="mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900"
              disabled={!locked || busy}
              onChange={(e) =>
                setVitals((v) => ({ ...v, [field.key]: e.target.value }))
              }
              value={vitals[field.key]}
            />
          </label>
        ))}
        <label className="block text-xs uppercase tracking-wide text-slate-500 sm:col-span-2">
          Notes
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
            disabled={!locked || busy}
            onChange={(e) => setNotes(e.target.value)}
            value={notes}
          />
        </label>
        <button
          className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60 sm:col-span-2"
          disabled={!locked || busy}
          type="submit"
        >
          {busy ? "Saving…" : "Save vitals"}
        </button>
      </form>

      {!locked ? (
        <p className="mt-3 text-sm text-slate-400">Select a patient first.</p>
      ) : null}
      {status ? (
        <p className="mt-3 break-words text-sm text-slate-700" role="status">
          {status}
        </p>
      ) : null}
    </section>
  );
}
