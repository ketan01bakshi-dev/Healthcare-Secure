"use client";

import { useCallback, useState } from "react";

import { usePatient } from "@/context/PatientContext";
import PrescriptionShare from "@/components/PrescriptionShare";
import VoiceRecorder from "@/components/VoiceRecorder";
import { getPrefillDoctorName } from "@/components/DoctorGate";
import { apiFetch } from "@/lib/doctorSession";

type TranscriptItem = {
  id: string;
  text: string;
  at: number;
};

type MedicationDraft = {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
};

type ClinicalDraft = {
  symptoms: string[];
  clinical_observations: string[];
  diagnoses: string[];
  medications: MedicationDraft[];
};

function linesToText(lines: string[]): string {
  return lines.join("\n");
}

function textToLines(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export default function EncounterWorkspace() {
  const { locked, rawIdentifier, patientPhone, bumpHistory } = usePatient();
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [parsing, setParsing] = useState(false);
  const [signing, setSigning] = useState(false);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [draft, setDraft] = useState<ClinicalDraft | null>(null);
  const [doctorName, setDoctorName] = useState("");

  const onTranscript = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setTranscripts((prev) => [
      ...prev,
      { id: `${Date.now()}-${prev.length}`, text: trimmed, at: Date.now() },
    ]);
  }, []);

  const removeTranscript = useCallback((id: string) => {
    setTranscripts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearSession = useCallback(() => {
    setTranscripts([]);
    setPdfBase64(null);
    setDownloadUrl(null);
    setWriteError(null);
    setDraft(null);
  }, []);

  const parseForReview = useCallback(async () => {
    if (!locked || !rawIdentifier.trim()) {
      setWriteError("Select a patient before preparing the prescription.");
      return;
    }
    if (transcripts.length === 0) {
      setWriteError("Record at least one voice note first.");
      return;
    }
    setParsing(true);
    setWriteError(null);
    setPdfBase64(null);
    setDownloadUrl(null);
    try {
      const response = await apiFetch("/api/v1/prescription/parse", {
        method: "POST",
        body: JSON.stringify({
          transcripts: transcripts.map((t) => t.text),
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Parse failed (${response.status})`);
      }
      const data = (await response.json()) as {
        clinical?: ClinicalDraft;
      };
      const clinical = data.clinical;
      if (!clinical) {
        throw new Error("Parse response missing clinical fields");
      }
      setDraft({
        symptoms: clinical.symptoms || [],
        clinical_observations: clinical.clinical_observations || [],
        diagnoses: clinical.diagnoses || [],
        medications: (clinical.medications || []).map((m) => ({
          name: m.name || "",
          dosage: m.dosage || "",
          frequency: m.frequency || "",
          duration: m.duration || "",
        })),
      });
      if (!doctorName.trim()) {
        setDoctorName(getPrefillDoctorName());
      }
    } catch (err) {
      setWriteError(err instanceof Error ? err.message : "Could not parse.");
    } finally {
      setParsing(false);
    }
  }, [doctorName, locked, rawIdentifier, transcripts]);

  const signPrescription = useCallback(async () => {
    if (!locked || !rawIdentifier.trim()) {
      setWriteError("Select a patient before signing.");
      return;
    }
    if (!draft) {
      setWriteError("Parse and review clinical fields first.");
      return;
    }
    setSigning(true);
    setWriteError(null);
    try {
      const response = await apiFetch("/api/v1/prescription/write", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier.trim(),
          doctor_name: doctorName.trim(),
          transcript_count: transcripts.length,
          clinical: draft,
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Sign failed (${response.status})`);
      }
      const data = (await response.json()) as {
        pdf_base64?: string;
        download_url?: string;
      };
      setPdfBase64(data.pdf_base64 ?? null);
      setDownloadUrl(data.download_url ?? null);
      bumpHistory();
    } catch (err) {
      setWriteError(
        err instanceof Error ? err.message : "Could not sign prescription.",
      );
    } finally {
      setSigning(false);
    }
  }, [bumpHistory, doctorName, draft, locked, rawIdentifier, transcripts.length]);

  const updateMed = (
    index: number,
    field: keyof MedicationDraft,
    value: string,
  ) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const medications = prev.medications.map((m, i) =>
        i === index ? { ...m, [field]: value } : m,
      );
      return { ...prev, medications };
    });
  };

  return (
    <div className="mx-auto w-full max-w-md space-y-6 overflow-x-hidden">
      {!locked ? (
        <p className="rounded-xl border border-amber-400/30 bg-amber-950/30 px-4 py-3 text-sm text-amber-100/90">
          Select a patient at the top before recording or writing a
          prescription.
        </p>
      ) : null}

      <VoiceRecorder disabled={!locked} onTranscript={onTranscript} />

      <section
        aria-label="Voice notes"
        className="rounded-2xl border border-clinical-100/15 bg-clinical-900/40 px-4 py-5 sm:px-6"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-clinical-50">
            Voice notes ({transcripts.length})
          </h2>
          {transcripts.length > 0 ? (
            <button
              className="min-h-12 rounded-lg px-3 text-sm text-clinical-100/70 active:text-clinical-50"
              onClick={clearSession}
              type="button"
            >
              Clear
            </button>
          ) : null}
        </div>
        <p className="mt-1 text-sm text-clinical-100/60">
          Record the visit, then prepare for review and sign.
        </p>

        {transcripts.length === 0 ? (
          <p className="mt-4 text-sm text-clinical-100/45">No voice notes yet.</p>
        ) : (
          <ol className="mt-4 space-y-3">
            {transcripts.map((item, index) => (
              <li
                key={item.id}
                className="rounded-lg border border-clinical-100/10 bg-black/20 px-3 py-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs uppercase tracking-wide text-clinical-100/50">
                    Note {index + 1}
                  </p>
                  <button
                    className="min-h-12 min-w-12 text-xs text-red-300"
                    onClick={() => removeTranscript(item.id)}
                    type="button"
                  >
                    Remove
                  </button>
                </div>
                <p className="mt-1 break-words text-sm text-clinical-50">
                  {item.text}
                </p>
              </li>
            ))}
          </ol>
        )}

        <button
          className="mt-5 inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-semibold text-white active:bg-clinical-700 disabled:opacity-60"
          disabled={!locked || parsing || transcripts.length === 0}
          onClick={() => void parseForReview()}
          type="button"
        >
          {parsing ? "Preparing…" : "Prepare for review"}
        </button>

        {writeError ? (
          <p className="mt-3 break-words text-sm text-red-300" role="alert">
            {writeError}
          </p>
        ) : null}
      </section>

      {draft ? (
        <section
          aria-label="Review clinical fields"
          className="rounded-2xl border border-clinical-500/30 bg-clinical-900/50 px-4 py-5 sm:px-6"
        >
          <h2 className="text-lg font-semibold text-clinical-50">
            Review before sign
          </h2>
          <p className="mt-1 text-sm text-clinical-100/60">
            Check and edit the details below, then sign to create the
            prescription PDF.
          </p>

          <label className="mt-4 block text-xs uppercase tracking-wide text-clinical-100/50">
            Doctor name on Rx
            <input
              className="mt-1 min-h-12 w-full rounded-lg border border-clinical-100/20 bg-black/25 px-3 text-sm text-clinical-50"
              onChange={(e) => setDoctorName(e.target.value)}
              value={doctorName}
            />
          </label>

          <label className="mt-3 block text-xs uppercase tracking-wide text-clinical-100/50">
            Diagnoses (one per line)
            <textarea
              className="mt-1 min-h-20 w-full rounded-lg border border-clinical-100/20 bg-black/25 px-3 py-2 text-sm text-clinical-50"
              onChange={(e) =>
                setDraft((d) =>
                  d ? { ...d, diagnoses: textToLines(e.target.value) } : d,
                )
              }
              value={linesToText(draft.diagnoses)}
            />
          </label>

          <label className="mt-3 block text-xs uppercase tracking-wide text-clinical-100/50">
            Symptoms (one per line)
            <textarea
              className="mt-1 min-h-16 w-full rounded-lg border border-clinical-100/20 bg-black/25 px-3 py-2 text-sm text-clinical-50"
              onChange={(e) =>
                setDraft((d) =>
                  d ? { ...d, symptoms: textToLines(e.target.value) } : d,
                )
              }
              value={linesToText(draft.symptoms)}
            />
          </label>

          <label className="mt-3 block text-xs uppercase tracking-wide text-clinical-100/50">
            Clinical observations (one per line)
            <textarea
              className="mt-1 min-h-16 w-full rounded-lg border border-clinical-100/20 bg-black/25 px-3 py-2 text-sm text-clinical-50"
              onChange={(e) =>
                setDraft((d) =>
                  d
                    ? {
                        ...d,
                        clinical_observations: textToLines(e.target.value),
                      }
                    : d,
                )
              }
              value={linesToText(draft.clinical_observations)}
            />
          </label>

          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-wide text-clinical-100/50">
                Medications
              </p>
              <button
                className="text-xs text-clinical-100/70"
                onClick={() =>
                  setDraft((d) =>
                    d
                      ? {
                          ...d,
                          medications: [
                            ...d.medications,
                            { name: "", dosage: "", frequency: "", duration: "" },
                          ],
                        }
                      : d,
                  )
                }
                type="button"
              >
                Add med
              </button>
            </div>
            {draft.medications.length === 0 ? (
              <p className="text-sm text-clinical-100/45">No medications yet.</p>
            ) : (
              draft.medications.map((med, index) => (
                <div
                  className="space-y-2 rounded-lg border border-clinical-100/10 bg-black/20 p-3"
                  key={`med-${index}`}
                >
                  {(["name", "dosage", "frequency", "duration"] as const).map(
                    (field) => (
                      <input
                        aria-label={`Medication ${field}`}
                        className="min-h-11 w-full rounded border border-clinical-100/15 bg-black/30 px-2 text-sm text-clinical-50"
                        key={field}
                        onChange={(e) => updateMed(index, field, e.target.value)}
                        placeholder={field}
                        value={med[field]}
                      />
                    ),
                  )}
                  <button
                    className="text-xs text-red-300"
                    onClick={() =>
                      setDraft((d) =>
                        d
                          ? {
                              ...d,
                              medications: d.medications.filter(
                                (_, i) => i !== index,
                              ),
                            }
                          : d,
                      )
                    }
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              ))
            )}
          </div>

          <button
            className="mt-5 inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
            disabled={signing}
            onClick={() => void signPrescription()}
            type="button"
          >
            {signing ? "Signing…" : "Sign prescription"}
          </button>
        </section>
      ) : null}

      {(pdfBase64 || downloadUrl) && (
        <PrescriptionShare
          doctorName={doctorName.trim() || "Clinic"}
          downloadUrl={downloadUrl}
          patientPhone={patientPhone}
          pdfBase64={pdfBase64}
        />
      )}
    </div>
  );
}
