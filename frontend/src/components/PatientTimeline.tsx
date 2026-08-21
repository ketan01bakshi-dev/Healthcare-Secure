"use client";

import { useCallback, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { formatIst } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { openAttachmentNative } from "@/lib/fileActions";
import { useI18n } from "@/lib/i18n";

type Medication = {
  name?: string;
  dosage?: string;
  frequency?: string;
  duration?: string;
};

type EncounterData = {
  type?: string;
  document_kind?: string;
  title?: string;
  filename?: string;
  has_content?: boolean;
  amount_inr?: number;
  note?: string;
  kind?: string;
  diagnoses?: unknown;
  diagnosis?: unknown;
  clinical_observations?: unknown;
  clinical_notes?: unknown;
  notes?: unknown;
  symptoms?: unknown;
  medications?: unknown;
  transcript_count?: number;
  vitals?: Record<string, string>;
  diagnostic_notes?: string;
  room_name?: string;
  entered_by?: { user_id?: string; display_name?: string; role?: string };
  signed_by?: { user_id?: string; display_name?: string; role?: string };
};

type HistoryRecord = {
  id: string;
  blind_patient_id: string;
  created_at: string | null;
  encounter_data: EncounterData | null;
};

type Status = "idle" | "loading" | "ready" | "empty" | "error";

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function asMedications(value: unknown): Medication[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(
      (item): item is Record<string, unknown> =>
        !!item && typeof item === "object",
    )
    .map((item) => ({
      name: typeof item.name === "string" ? item.name : undefined,
      dosage: typeof item.dosage === "string" ? item.dosage : undefined,
      frequency: typeof item.frequency === "string" ? item.frequency : undefined,
      duration: typeof item.duration === "string" ? item.duration : undefined,
    }))
    .filter((m) => m.name);
}

function formatVisitDate(iso: string | null): string {
  return formatIst(iso);
}

function summarizeNotes(data: EncounterData | null): string {
  if (!data) return "No clinical notes recorded for this visit.";
  if (data.type === "document") {
    return (
      data.title ||
      data.filename ||
      `Uploaded ${data.document_kind?.replace(/_/g, " ") || "document"}`
    );
  }
  if (data.type === "vitals") {
    const vitals = data.vitals || {};
    const parts = Object.entries(vitals)
      .filter(([, v]) => typeof v === "string" && v.trim())
      .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`);
    if (data.diagnostic_notes?.trim()) {
      parts.push(`Notes: ${data.diagnostic_notes.trim()}`);
    }
    return parts.join(" · ") || "Vitals entry";
  }
  if (data.type === "video_consult") {
    return data.room_name
      ? `Video consult · ${data.room_name}`
      : "Video consult";
  }
  if (data.type === "lab_result") {
    return asStringList(data.clinical_observations).join(" · ") || "Lab result";
  }
  if (data.type === "billing") {
    const amount = data.amount_inr;
    const note =
      typeof data.note === "string" && data.note.trim() ? data.note.trim() : "";
    const kind =
      data.kind === "payment"
        ? "Payment"
        : data.kind === "charge"
          ? "Charge"
          : "Bill";
    const amountText =
      typeof amount === "number"
        ? `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`
        : kind;
    const labeled = `${kind} ${amountText}`;
    return note ? `${labeled} — ${note}` : labeled;
  }
  const observations = asStringList(data.clinical_observations);
  const notes = asStringList(data.clinical_notes);
  const legacyNotes = asStringList(data.notes);
  const symptoms = asStringList(data.symptoms);
  const parts = [...observations, ...notes, ...legacyNotes];
  if (parts.length) return parts.join(" · ");
  if (symptoms.length) return `Symptoms: ${symptoms.join(", ")}`;
  return "No clinical notes recorded for this visit.";
}

function actorLabel(data: EncounterData): string | null {
  const actor = data.entered_by || data.signed_by;
  if (!actor?.display_name && !actor?.user_id) return null;
  const name = actor.display_name || "Team member";
  const role =
    actor.role === "doctor"
      ? "Doctor"
      : actor.role === "staff"
        ? "Staff"
        : actor.role === "receptionist"
          ? "Reception"
          : actor.role === "lab"
          ? "Lab"
          : null;
  return role ? `${name} (${role})` : name;
}

function TimelineSkeleton() {
  return (
    <ol className="relative mt-10 space-y-8 border-l border-clinical-100/20 pl-6 sm:pl-8">
      {[0, 1, 2].map((i) => (
        <li key={i} className="relative animate-pulse">
          <span className="absolute -left-[1.55rem] top-1 h-3 w-3 rounded-full bg-clinical-100/25 sm:-left-[2.05rem]" />
          <div className="h-3 w-32 rounded bg-clinical-100/15" />
          <div className="mt-3 flex flex-wrap gap-2">
            <div className="h-6 w-20 rounded-full bg-clinical-100/15" />
            <div className="h-6 w-24 rounded-full bg-clinical-100/15" />
          </div>
          <div className="mt-4 h-16 rounded-lg bg-clinical-100/10" />
        </li>
      ))}
    </ol>
  );
}

export default function PatientTimeline() {
  const { t } = useI18n();
  const { locked, rawIdentifier, historyVersion } = usePatient();
  const [status, setStatus] = useState<Status>("idle");
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async (raw: string) => {
    setStatus("loading");
    setError(null);
    setRecords([]);
    try {
      const response = await apiFetch("/api/v1/history/search", {
        method: "POST",
        body: JSON.stringify({ raw_identifier: raw }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Search failed (${response.status})`);
      }
      const data = (await response.json()) as HistoryRecord[];
      if (!Array.isArray(data) || data.length === 0) {
        setRecords([]);
        setStatus("empty");
        return;
      }
      setRecords(data);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(
        err instanceof Error ? err.message : "Unable to search patient history.",
      );
    }
  }, []);

  useEffect(() => {
    if (!locked || !rawIdentifier.trim()) {
      setStatus("idle");
      setRecords([]);
      setError(null);
      return;
    }
    void loadHistory(rawIdentifier.trim());
  }, [locked, rawIdentifier, historyVersion, loadHistory]);

  async function openDocument(recordId: string) {
    if (!rawIdentifier.trim()) return;
    const response = await apiFetch(
      `/api/v1/history/documents/${recordId}/content`,
      {
        method: "POST",
        body: JSON.stringify({ raw_identifier: rawIdentifier.trim() }),
      },
    );
    if (!response.ok) {
      throw new Error(`Could not open document (${response.status})`);
    }
    const blob = await response.blob();
    const filename = `document-${recordId.slice(0, 8)}`;
    await openAttachmentNative(blob, filename);
  }

  return (
    <CollapsibleSection
      aria-label={t("patientTimeline")}
      className="mx-auto w-full max-w-3xl rounded-2xl border border-clinical-100/15 bg-clinical-900/40 px-4 py-8 shadow-lg backdrop-blur-sm sm:px-8"
      hint={t("patientTimelineHint")}
      title={t("patientTimeline")}
      variant="dark"
    >
      {!locked ? (
        <p className="text-center text-sm text-clinical-100/45">
          {t("selectPatientForHistory")}
        </p>
      ) : null}

      {status === "loading" ? <TimelineSkeleton /> : null}

      {status === "error" && error ? (
        <p className="mt-6 text-sm text-red-300" role="alert">
          {error}
        </p>
      ) : null}

      {status === "empty" ? (
        <div className="mt-10 rounded-xl border border-dashed border-clinical-100/20 px-6 py-12 text-center">
          <p className="text-base font-medium text-clinical-50">
            {t("noHistoryYet")}
          </p>
          <p className="mt-2 text-sm text-clinical-100/60">
            {t("noHistoryHint")}
          </p>
        </div>
      ) : null}

      {status === "ready" ? (
        <ol className="relative mt-10 space-y-10 border-l border-clinical-500/40 pl-6 sm:pl-8">
          {records.map((record) => {
            const data = record.encounter_data ?? {};
            const isDoc = data.type === "document";
            const isVitals = data.type === "vitals";
            const diagnoses = [
              ...asStringList(data.diagnoses),
              ...asStringList(data.diagnosis),
            ];
            const medications = asMedications(data.medications);
            const notes = summarizeNotes(data);
            const who = actorLabel(data);
            const kindLabel = isDoc
              ? (data.document_kind || "document").replace(/_/g, " ")
              : isVitals
                ? "vitals"
                : data.type === "lab_result"
                  ? "lab result"
                  : data.type === "billing"
                    ? data.kind === "payment"
                      ? "payment"
                      : data.kind === "charge"
                        ? "charge"
                        : "billing"
                    : data.type === "health_profile"
                      ? "health profile"
                      : data.type === "obstetric_profile"
                        ? "obstetric"
                        : data.type === "abha_link"
                          ? "ABHA"
                          : data.type === "audit"
                            ? "activity"
                            : data.type === "prescription"
                              ? "prescription"
                              : "visit";

            return (
              <li className="relative" key={record.id}>
                <span
                  aria-hidden
                  className="absolute -left-[1.6rem] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-clinical-500 bg-clinical-500 shadow-[0_0_0_4px_rgba(42,111,106,0.15)] sm:-left-[2.1rem]"
                />

                <time
                  className="text-xs font-medium uppercase tracking-wide text-slate-500"
                  dateTime={record.created_at ?? undefined}
                >
                  {formatVisitDate(record.created_at)} · {kindLabel}
                </time>
                {who ? (
                  <p className="mt-1 text-xs text-slate-600">
                    Updated by <span className="font-medium text-slate-800">{who}</span>
                  </p>
                ) : null}

                <div className="mt-3 flex flex-wrap gap-2">
                  {isDoc ? (
                    <span className="rounded-full border border-clinical-500/40 bg-clinical-500/20 px-3 py-1 text-xs font-medium text-clinical-50">
                      {kindLabel}
                    </span>
                  ) : diagnoses.length ? (
                    diagnoses.map((dx) => (
                      <span
                        className="rounded-full border border-clinical-500/40 bg-clinical-500/20 px-3 py-1 text-xs font-medium text-clinical-50"
                        key={`${record.id}-${dx}`}
                      >
                        {dx}
                      </span>
                    ))
                  ) : (
                    <span className="rounded-full border border-clinical-100/15 px-3 py-1 text-xs text-clinical-100/50">
                      No diagnosis listed
                    </span>
                  )}
                </div>

                <div className="mt-4 rounded-lg border border-clinical-100/15 bg-black/20 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-wide text-clinical-100/50">
                    {isDoc ? "Document" : "Clinical notes"}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-clinical-100/90">
                    {notes}
                  </p>
                  {isDoc && data.has_content ? (
                    <button
                      className="mt-3 inline-flex min-h-12 items-center rounded-lg border border-clinical-100/25 px-3 text-sm text-clinical-50"
                      onClick={() => void openDocument(record.id).catch((e) => setError(String(e)))}
                      type="button"
                    >
                      Open file
                    </button>
                  ) : null}
                  {!isDoc && !isVitals && data.transcript_count ? (
                    <p className="mt-2 text-xs text-slate-500">
                      From voice notes
                    </p>
                  ) : null}
                </div>

                {!isDoc && !isVitals ? (
                  <div className="mt-4">
                    <p className="text-[11px] uppercase tracking-wide text-slate-500">
                      Medications
                    </p>
                    {medications.length ? (
                      <ul className="mt-2 space-y-2">
                        {medications.map((med, index) => (
                          <li
                            className="rounded-md border border-clinical-100/10 bg-clinical-900/50 px-3 py-2 text-sm text-clinical-50"
                            key={`${record.id}-med-${index}`}
                          >
                            <span className="font-medium">{med.name}</span>
                            <span className="mt-0.5 block text-xs text-clinical-100/65">
                              {[med.dosage, med.frequency, med.duration]
                                .filter(Boolean)
                                .join(" · ") || "Details not specified"}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-clinical-100/50">
                        No medications recorded.
                      </p>
                    )}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : null}
    </CollapsibleSection>
  );
}
