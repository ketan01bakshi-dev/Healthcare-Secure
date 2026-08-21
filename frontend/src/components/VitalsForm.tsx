"use client";

import { FormEvent, useMemo, useState } from "react";

import { apiFetch, getClinicUser } from "@/lib/doctorSession";
import {
  hasVitalsErrors,
  type VitalsFieldKey,
  type VitalsFields,
  validateAllVitals,
  validateNotes,
  validateVitalField,
  hasAnyVitalOrNotes,
} from "@/lib/vitalsValidation";
import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { useI18n } from "@/lib/i18n";

const EMPTY: VitalsFields = {
  blood_pressure: "",
  pulse: "",
  temperature: "",
  spo2: "",
  weight: "",
  height: "",
  respiratory_rate: "",
  hemoglobin: "",
};

type FieldErrors = Partial<Record<VitalsFieldKey | "notes", string>>;

const FIELD_KEYS: VitalsFieldKey[] = [
  "blood_pressure",
  "pulse",
  "temperature",
  "spo2",
  "weight",
  "height",
  "respiratory_rate",
  "hemoglobin",
];

const FIELD_LABEL_KEYS: Record<VitalsFieldKey, string> = {
  blood_pressure: "vitalBp",
  pulse: "vitalPulse",
  temperature: "vitalTemperature",
  spo2: "vitalSpo2",
  weight: "vitalWeight",
  height: "vitalHeight",
  respiratory_rate: "vitalRespRate",
  hemoglobin: "vitalHb",
};

type TempUnit = "F" | "C";
const TEMP_KEY = "healthcare_temp_unit";

function parseApiError(text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: string | unknown[] };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      const first = parsed.detail[0] as { msg?: string };
      if (typeof first?.msg === "string") return first.msg;
    }
  } catch {
    /* keep raw text */
  }
  return text.trim() || "Could not save vitals.";
}

function isOfflineRetryable(status: number): boolean {
  return status >= 500 || status === 408 || status === 429;
}

export default function VitalsForm() {
  const { t } = useI18n();
  const { locked, rawIdentifier, bumpHistory, patientAgeYears } = usePatient();
  const [vitals, setVitals] = useState<VitalsFields>(EMPTY);
  const [notes, setNotes] = useState("");
  const [tempUnit, setTempUnit] = useState<TempUnit>(() => {
    if (typeof window === "undefined") return "F";
    return localStorage.getItem(TEMP_KEY) === "C" ? "C" : "F";
  });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const invalid = useMemo(() => hasVitalsErrors(errors), [errors]);

  function setUnit(u: TempUnit) {
    setTempUnit(u);
    try {
      localStorage.setItem(TEMP_KEY, u);
    } catch {
      /* ignore */
    }
    if (vitals.temperature) {
      const err = validateVitalField("temperature", vitals.temperature, {
        temperatureUnit: u,
      });
      setErrors((prev) => {
        const next = { ...prev };
        if (err) next.temperature = err;
        else delete next.temperature;
        return next;
      });
    }
  }

  function setVital(key: VitalsFieldKey, value: string) {
    setVitals((prev) => ({ ...prev, [key]: value }));
    const err = validateVitalField(key, value, { temperatureUnit: tempUnit });
    setErrors((prev) => {
      const next = { ...prev };
      if (err) next[key] = err;
      else delete next[key];
      return next;
    });
  }

  function onNotesChange(value: string) {
    setNotes(value);
    const err = validateNotes(value);
    setErrors((prev) => {
      const next = { ...prev };
      if (err) next.notes = err;
      else delete next.notes;
      return next;
    });
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!locked || !rawIdentifier.trim()) {
      setStatus("Select a patient first.");
      return;
    }
    const nextErrors = validateAllVitals(vitals, notes, {
      temperatureUnit: tempUnit,
    });
    setErrors(nextErrors);
    if (hasVitalsErrors(nextErrors)) {
      setStatus("Please fix the highlighted fields.");
      return;
    }
    if (!hasAnyVitalOrNotes(vitals, notes)) {
      setStatus("Enter at least one vital or a note.");
      return;
    }
    setBusy(true);
    setStatus(null);
    const age =
      patientAgeYears.trim() === ""
        ? null
        : Number.parseFloat(patientAgeYears.trim());
    const payload = {
      raw_identifier: rawIdentifier.trim(),
      vitals,
      diagnostic_notes: notes.trim(),
      age_years: age !== null && Number.isFinite(age) ? age : null,
      temperature_unit: tempUnit,
    };
    try {
      const response = await apiFetch("/api/v1/history/vitals", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        const detail = parseApiError(text);
        if (isOfflineRetryable(response.status)) {
          const { enqueueOffline } = await import("@/lib/offlineQueue");
          enqueueOffline("/api/v1/history/vitals", payload);
          setStatus("Saved offline — will sync when the server is back.");
          setVitals(EMPTY);
          setNotes("");
        } else {
          setStatus(detail);
        }
        return;
      }
      const user = getClinicUser();
      setStatus(
        `Saved${user ? ` as ${user.display_name}` : ""}. Visible on the timeline with your name.`,
      );
      setVitals(EMPTY);
      setNotes("");
      setErrors({});
      bumpHistory();
    } catch {
      const { enqueueOffline } = await import("@/lib/offlineQueue");
      enqueueOffline("/api/v1/history/vitals", payload);
      setStatus("Saved offline — will sync when the server is back.");
      setVitals(EMPTY);
      setNotes("");
    } finally {
      setBusy(false);
    }
  }

  if (!locked) return null;

  return (
    <CollapsibleSection
      aria-label={t("vitalsNotes")}
      hint={t("vitalsNotesHint")}
      title={t("vitalsNotes")}
    >
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={onSubmit}>
        <label className="block text-xs uppercase tracking-wide text-slate-500 sm:col-span-2">
          {t("tempUnit")}
          <select
            aria-label={t("tempUnit")}
            className="mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm"
            disabled={busy}
            onChange={(e) => setUnit(e.target.value as TempUnit)}
            value={tempUnit}
          >
            <option value="F">{t("tempFahrenheit")}</option>
            <option value="C">{t("tempCelsius")}</option>
          </select>
        </label>
        {FIELD_KEYS.map((key) => {
          const err = errors[key];
          const label =
            key === "temperature"
              ? `${t("vitalTemperature")} (°${tempUnit})`
              : t(FIELD_LABEL_KEYS[key]);
          return (
            <label
              className="block text-xs uppercase tracking-wide text-slate-500"
              key={key}
            >
              {label}
              <input
                aria-invalid={!!err}
                className={`mt-1 min-h-11 w-full rounded-lg border bg-white px-3 text-sm text-slate-900 ${
                  err
                    ? "border-red-400 ring-1 ring-red-300"
                    : "border-slate-200"
                }`}
                disabled={busy}
                onBlur={() => {
                  const message = validateVitalField(key, vitals[key]);
                  setErrors((prev) => {
                    const next = { ...prev };
                    if (message) next[key] = message;
                    else delete next[key];
                    return next;
                  });
                }}
                onChange={(e) => setVital(key, e.target.value)}
                placeholder={
                  key === "blood_pressure" ? "e.g. 120/80" : undefined
                }
                value={vitals[key]}
              />
              {err ? (
                <span className="mt-1 block normal-case tracking-normal text-red-600">
                  {err}
                </span>
              ) : null}
            </label>
          );
        })}
        <label className="block text-xs uppercase tracking-wide text-slate-500 sm:col-span-2">
          {t("diagnosticNotes")}
          <textarea
            aria-invalid={!!errors.notes}
            className={`mt-1 min-h-24 w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 ${
              errors.notes
                ? "border-red-400 ring-1 ring-red-300"
                : "border-slate-200"
            }`}
            disabled={busy}
            onChange={(e) => onNotesChange(e.target.value)}
            value={notes}
          />
          {errors.notes ? (
            <span className="mt-1 block normal-case tracking-normal text-red-600">
              {errors.notes}
            </span>
          ) : null}
        </label>
        <button
          className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60 sm:col-span-2"
          disabled={busy || invalid}
          type="submit"
        >
          {busy ? t("savingEllipsis") : t("saveVitals")}
        </button>
      </form>

      {status ? (
        <p
          className={`mt-3 break-words text-sm ${
            invalid && status.startsWith("Please fix")
              ? "text-red-600"
              : "text-slate-700"
          }`}
          role="status"
        >
          {status}
        </p>
      ) : null}
    </CollapsibleSection>
  );
}
