"use client";

import { FormEvent, useMemo, useState } from "react";

import { usePatient } from "@/context/PatientContext";

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "").slice(0, 10);
}

export default function PatientBar() {
  const {
    nameDraft,
    phoneDraft,
    patientName,
    patientPhone,
    locked,
    setNameDraft,
    setPhoneDraft,
    lockPatient,
    clearPatient,
  } = usePatient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onLock(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await lockPatient();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not select patient.");
    } finally {
      setBusy(false);
    }
  }

  const digitCount = useMemo(
    () => phoneDraft.replace(/\D+/g, "").length,
    [phoneDraft],
  );
  const canLock = nameDraft.trim().length > 0 && digitCount === 10;

  return (
    <section
      aria-label="Patient identity"
      className="mx-auto w-full max-w-3xl overflow-x-hidden rounded-2xl border border-slate-200 bg-white px-4 py-5 shadow-sm sm:px-6"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        Patient
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        Enter the patient&apos;s full name and 10-digit mobile number to begin.
      </p>

      {!locked ? (
        <form className="mt-4 flex flex-col gap-3" onSubmit={onLock}>
          <input
            aria-label="Patient name"
            autoComplete="off"
            className="min-h-12 w-full rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none ring-clinical-500 focus:ring-2"
            onChange={(e) => setNameDraft(e.target.value)}
            placeholder="Patient full name"
            value={nameDraft}
          />
          <div>
            <input
              aria-label="Patient phone number"
              autoComplete="tel"
              className="min-h-12 w-full rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none ring-clinical-500 focus:ring-2"
              inputMode="numeric"
              maxLength={14}
              onChange={(e) => setPhoneDraft(digitsOnly(e.target.value))}
              placeholder="10-digit mobile number"
              type="tel"
              value={phoneDraft}
            />
            {digitCount > 0 && digitCount !== 10 ? (
              <p className="mt-1 text-xs text-amber-700">
                Please enter all 10 digits of the mobile number.
              </p>
            ) : null}
          </div>
          <button
            className="inline-flex min-h-12 min-w-[48px] items-center justify-center rounded-lg bg-clinical-500 px-5 text-sm font-medium text-white disabled:opacity-60"
            disabled={busy || !canLock}
            type="submit"
          >
            {busy ? "Please wait…" : "Select patient"}
          </button>
        </form>
      ) : (
        <div className="mt-4 space-y-3">
          <p className="text-base font-medium text-slate-900">
            {patientName}
          </p>
          <p className="text-sm text-slate-700">Mobile: {patientPhone}</p>
          <button
            className="inline-flex min-h-12 items-center justify-center rounded-lg border border-slate-200 px-4 text-sm text-slate-800"
            onClick={clearPatient}
            type="button"
          >
            Change patient
          </button>
        </div>
      )}

      {error ? (
        <p className="mt-3 text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
