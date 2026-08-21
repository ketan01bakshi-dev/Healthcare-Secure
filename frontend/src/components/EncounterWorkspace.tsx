"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import PrescriptionShare from "@/components/PrescriptionShare";
import VoiceRecorder from "@/components/VoiceRecorder";
import { getPrefillDoctorName, useClinicFeatures } from "@/components/DoctorGate";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";
import {
  ALPHA_RECOMMENDED_DIAGNOSTICS,
  formatInvestigationsLine,
  stripInvestigationsLine,
} from "@/lib/recommendedDiagnostics";

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

type RxMode = "voice" | "text";
type RxStep = "capture" | "review" | "share";

const EMPTY_MED: MedicationDraft = {
  name: "",
  dosage: "",
  frequency: "",
  duration: "",
};

const EMPTY_DRAFT: ClinicalDraft = {
  symptoms: [],
  clinical_observations: [],
  diagnoses: [],
  medications: [],
};

const GYNAE_DEMO_SCRIPTS: { id: string; label: string; text: string }[] = [
  {
    id: "dys",
    label: "Demo: Dysmenorrhea Rx",
    text:
      "Severe lower abdominal pain and heavy menstrual flow for three days. " +
      "Abdomen soft, tender hypogastrium. Diagnosis primary dysmenorrhea and menorrhagia. " +
      "Mefenamic acid five hundred milligrams three times a day after food for three days. " +
      "Tranexamic acid five hundred milligrams three times a day for five days.",
  },
  {
    id: "anc",
    label: "Demo: ANC 28w Rx",
    text:
      "Antenatal care at twenty eight weeks. Mild backache and fatigue. " +
      "Fundal height appropriate, fetal heart rate present. Mild anemia. " +
      "Iron folic acid one tablet once daily after food for thirty days. " +
      "Calcium five hundred milligrams twice daily for thirty days. " +
      "Labetalol one hundred milligrams twice daily for seven days.",
  },
  {
    id: "pcos",
    label: "Demo: PCOS Rx",
    text:
      "Irregular cycles, acne, and weight gain. PCOS and infertility workup. " +
      "Metformin five hundred milligrams twice daily after food for ninety days. " +
      "Myo-inositol two grams twice daily for ninety days.",
  },
];

const GP_DEMO_SCRIPTS: { id: string; label: string; text: string }[] = [
  {
    id: "urti",
    label: "Demo: URTI Rx",
    text:
      "Cough, fever, and sore throat for three days. Throat congested, chest clear on auscultation. " +
      "Diagnosis acute upper respiratory tract infection. " +
      "Paracetamol five hundred milligrams three times a day after food for three days. " +
      "Azithromycin five hundred milligrams once daily for three days.",
  },
  {
    id: "dm",
    label: "Demo: Type 2 DM follow-up",
    text:
      "Known type two diabetes mellitus follow-up. Fasting sugar one twelve milligrams per deciliter. " +
      "HbA one c six point nine percent. No hypoglycemia. " +
      "Continue metformin five hundred milligrams twice daily after food for ninety days. " +
      "Atorvastatin ten milligrams once at night for ninety days.",
  },
  {
    id: "htn",
    label: "Demo: Hypertension Rx",
    text:
      "Essential hypertension with headache and dizziness. Blood pressure one sixty two over one oh four. " +
      "Amlodipine five milligrams once daily for thirty days. " +
      "Telmisartan forty milligrams once daily for thirty days.",
  },
];

const FIELD =
  "mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900";
const AREA =
  "mt-1 min-h-16 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900";
const LABEL =
  "block text-xs font-medium uppercase tracking-wide text-slate-500";

function linesToText(lines: string[]): string {
  return lines.join("\n");
}

function textToLines(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

function draftHasContent(d: ClinicalDraft): boolean {
  return (
    d.diagnoses.length > 0 ||
    d.symptoms.length > 0 ||
    d.clinical_observations.length > 0 ||
    d.medications.some((m) =>
      [m.name, m.dosage, m.frequency, m.duration].some((v) => v.trim()),
    )
  );
}

function mergeInvestigations(
  draft: ClinicalDraft,
  selectedLabels: string[],
): ClinicalDraft {
  const stripped = stripInvestigationsLine(draft.clinical_observations);
  const line = formatInvestigationsLine(selectedLabels);
  return {
    ...draft,
    clinical_observations: line ? [...stripped, line] : stripped,
  };
}

function transcriptKey(items: TranscriptItem[]): string {
  return items.map((item) => item.id).join("\n");
}

function snapshotFromParsed(clinical: ClinicalDraft): ClinicalDraft {
  return {
    symptoms: clinical.symptoms || [],
    clinical_observations: clinical.clinical_observations || [],
    diagnoses: clinical.diagnoses || [],
    medications: (clinical.medications || []).map((m) => ({
      name: m.name || "",
      dosage: m.dosage || "",
      frequency: m.frequency || "",
      duration: m.duration || "",
    })),
  };
}

const PARSE_PREFETCH_MS = 500;

function MedicationsEditor({
  medications,
  onChange,
  disabled = false,
}: {
  medications: MedicationDraft[];
  onChange: (next: MedicationDraft[]) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Medications
        </p>
        <button
          className="text-xs text-slate-600"
          disabled={disabled}
          onClick={() => onChange([...medications, { ...EMPTY_MED }])}
          type="button"
        >
          Add med
        </button>
      </div>
      {medications.length === 0 ? (
        <p className="text-sm text-slate-400">{t("noMedicationsYet")}</p>
      ) : (
        medications.map((med, index) => (
          <div
            className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3"
            key={`med-${index}`}
          >
            {(["name", "dosage", "frequency", "duration"] as const).map(
              (field) => (
                <input
                  aria-label={`Medication ${field}`}
                  className="min-h-11 w-full rounded border border-slate-200 bg-white px-2 text-sm text-slate-900"
                  disabled={disabled}
                  key={field}
                  onChange={(e) => {
                    const next = medications.map((m, i) =>
                      i === index ? { ...m, [field]: e.target.value } : m,
                    );
                    onChange(next);
                  }}
                  placeholder={field}
                  value={med[field]}
                />
              ),
            )}
            <button
              className="text-xs text-red-600"
              disabled={disabled}
              onClick={() =>
                onChange(medications.filter((_, i) => i !== index))
              }
              type="button"
            >
              {t("remove")}
            </button>
          </div>
        ))
      )}
    </div>
  );
}

function StepTabs({
  step,
  canReview,
  canShare,
  onSelect,
  labels,
}: {
  step: RxStep;
  canReview: boolean;
  canShare: boolean;
  onSelect: (s: RxStep) => void;
  labels: { capture: string; review: string; share: string };
}) {
  const items: { id: RxStep; label: string; enabled: boolean }[] = [
    { id: "capture", label: labels.capture, enabled: true },
    { id: "review", label: labels.review, enabled: canReview },
    { id: "share", label: labels.share, enabled: canShare },
  ];
  return (
    <div
      aria-label="Prescription steps"
      className="flex rounded-lg border border-slate-200 bg-slate-100 p-1"
      role="tablist"
    >
      {items.map((item) => {
        const active = step === item.id;
        return (
          <button
            aria-selected={active}
            className={`min-h-11 flex-1 rounded-md px-1 text-[11px] font-medium transition-colors sm:text-sm ${
              active
                ? "bg-white text-slate-900 shadow-sm"
                : item.enabled
                  ? "text-slate-600 hover:text-slate-900"
                  : "cursor-not-allowed text-slate-400"
            }`}
            disabled={!item.enabled}
            key={item.id}
            onClick={() => onSelect(item.id)}
            role="tab"
            type="button"
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export default function EncounterWorkspace() {
  const { t } = useI18n();
  const { has } = useClinicFeatures();
  const demoScripts = has("obstetric") ? GYNAE_DEMO_SCRIPTS : GP_DEMO_SCRIPTS;
  const { locked, rawIdentifier, patientPhone, bumpHistory, selectedDiagnostics } =
    usePatient();
  const selectedDiagnosticLabels = useMemo(
    () =>
      ALPHA_RECOMMENDED_DIAGNOSTICS.filter((item) =>
        selectedDiagnostics.includes(item.id),
      ).map((item) => item.label),
    [selectedDiagnostics],
  );
  const [step, setStep] = useState<RxStep>("capture");
  const [mode, setMode] = useState<RxMode>("voice");
  const [demoOpen, setDemoOpen] = useState(false);
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [textForm, setTextForm] = useState<ClinicalDraft>(EMPTY_DRAFT);
  const [parsing, setParsing] = useState(false);
  const [signing, setSigning] = useState(false);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [draft, setDraft] = useState<ClinicalDraft | null>(null);
  const [parsedClinical, setParsedClinical] = useState<ClinicalDraft | null>(
    null,
  );
  const [sourceLanguage, setSourceLanguage] = useState<"en" | "hi">("en");
  const [signTranscriptCount, setSignTranscriptCount] = useState(0);
  const [doctorName, setDoctorName] = useState("");
  const [rxHints, setRxHints] = useState<
    { severity: string; message: string }[]
  >([]);
  const [hintsChecked, setHintsChecked] = useState(false);
  const [checkingHints, setCheckingHints] = useState(false);
  const parsePrefetchRef = useRef<{
    key: string;
    promise: Promise<ClinicalDraft> | null;
    result: ClinicalDraft | null;
  }>({ key: "", promise: null, result: null });

  useEffect(() => {
    setTextForm((prev) => mergeInvestigations(prev, selectedDiagnosticLabels));
    setDraft((prev) =>
      prev ? mergeInvestigations(prev, selectedDiagnosticLabels) : prev,
    );
  }, [selectedDiagnosticLabels]);

  const onTranscript = useCallback(
    (text: string, meta?: { language?: "en" | "hi" }) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      if (meta?.language === "en" || meta?.language === "hi") {
        setSourceLanguage(meta.language);
      }
      setTranscripts((prev) => [
        ...prev,
        { id: `${Date.now()}-${prev.length}`, text: trimmed, at: Date.now() },
      ]);
    },
    [],
  );

  const removeTranscript = useCallback((id: string) => {
    setTranscripts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearSession = useCallback(() => {
    parsePrefetchRef.current = { key: "", promise: null, result: null };
    setTranscripts([]);
    setTextForm(EMPTY_DRAFT);
    setPdfBase64(null);
    setDownloadUrl(null);
    setWriteError(null);
    setDraft(null);
    setParsedClinical(null);
    setSourceLanguage("en");
    setSignTranscriptCount(0);
    setRxHints([]);
    setHintsChecked(false);
    setStep("capture");
  }, []);

  const ensureDoctorName = useCallback(() => {
    if (!doctorName.trim()) {
      setDoctorName(getPrefillDoctorName());
    }
  }, [doctorName]);

  const goToReview = useCallback(
    (
      next: ClinicalDraft,
      transcriptCount: number,
      parsedSnapshot?: ClinicalDraft | null,
    ) => {
      setDraft(next);
      if (parsedSnapshot !== undefined) {
        setParsedClinical(parsedSnapshot);
      }
      setSignTranscriptCount(transcriptCount);
      setRxHints([]);
      setHintsChecked(false);
      setPdfBase64(null);
      setDownloadUrl(null);
      ensureDoctorName();
      setStep("review");
    },
    [ensureDoctorName],
  );

  const requestParse = useCallback(async (texts: string[]): Promise<ClinicalDraft> => {
    const response = await apiFetch("/api/v1/prescription/parse", {
      method: "POST",
      body: JSON.stringify({ transcripts: texts }),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(text || `Parse failed (${response.status})`);
    }
    const data = (await response.json()) as { clinical?: ClinicalDraft };
    const clinical = data.clinical;
    if (!clinical) {
      throw new Error("Parse response missing clinical fields");
    }
    return snapshotFromParsed(clinical);
  }, []);

  useEffect(() => {
    if (mode !== "voice" || !locked || !rawIdentifier.trim()) {
      return;
    }
    if (transcripts.length === 0) {
      parsePrefetchRef.current = { key: "", promise: null, result: null };
      return;
    }
    const key = transcriptKey(transcripts);
    const timer = window.setTimeout(() => {
      const current = parsePrefetchRef.current;
      if (
        current.key === key &&
        (current.result || current.promise)
      ) {
        return;
      }
      const promise = requestParse(transcripts.map((item) => item.text));
      parsePrefetchRef.current = { key, promise, result: null };
      void promise
        .then((result) => {
          if (parsePrefetchRef.current.key === key) {
            parsePrefetchRef.current = { key, promise: null, result };
          }
        })
        .catch(() => {
          if (parsePrefetchRef.current.key === key) {
            parsePrefetchRef.current = { key: "", promise: null, result: null };
          }
        });
    }, PARSE_PREFETCH_MS);
    return () => window.clearTimeout(timer);
  }, [locked, mode, rawIdentifier, requestParse, transcripts]);

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
    try {
      const key = transcriptKey(transcripts);
      const prefetched = parsePrefetchRef.current;
      let snapshot: ClinicalDraft;
      if (prefetched.key === key && prefetched.result) {
        snapshot = prefetched.result;
      } else if (prefetched.key === key && prefetched.promise) {
        snapshot = await prefetched.promise;
      } else {
        snapshot = await requestParse(transcripts.map((item) => item.text));
      }
      goToReview(
        mergeInvestigations(
          {
            symptoms: [...snapshot.symptoms],
            clinical_observations: [...snapshot.clinical_observations],
            diagnoses: [...snapshot.diagnoses],
            medications: snapshot.medications.map((m) => ({ ...m })),
          },
          selectedDiagnosticLabels,
        ),
        transcripts.length,
        snapshot,
      );
    } catch (err) {
      setWriteError(err instanceof Error ? err.message : "Could not parse.");
    } finally {
      setParsing(false);
    }
  }, [
    goToReview,
    locked,
    rawIdentifier,
    requestParse,
    selectedDiagnosticLabels,
    transcripts,
  ]);

  const textToReview = useCallback(() => {
    if (!locked || !rawIdentifier.trim()) {
      setWriteError("Select a patient before preparing the prescription.");
      return;
    }
    if (!draftHasContent(textForm)) {
      setWriteError("Enter at least one diagnosis, note, or medication.");
      return;
    }
    setWriteError(null);
    goToReview(
      mergeInvestigations(
        {
          symptoms: [...textForm.symptoms],
          clinical_observations: [...textForm.clinical_observations],
          diagnoses: [...textForm.diagnoses],
          medications: textForm.medications.map((m) => ({ ...m })),
        },
        selectedDiagnosticLabels,
      ),
      0,
      null,
    );
  }, [goToReview, locked, rawIdentifier, selectedDiagnosticLabels, textForm]);

  const signPrescription = useCallback(
    async (opts?: { skipHints?: boolean }) => {
      if (!locked || !rawIdentifier.trim()) {
        setWriteError("Select a patient before signing.");
        return;
      }
      if (!draft) {
        setWriteError("Prepare and review clinical fields first.");
        return;
      }

      if (!opts?.skipHints && !hintsChecked) {
        setCheckingHints(true);
        setWriteError(null);
        try {
          const hintRes = await apiFetch("/api/v1/history/rx-hints", {
            method: "POST",
            body: JSON.stringify({
              raw_identifier: rawIdentifier.trim(),
              medications: draft.medications,
            }),
          });
          if (hintRes.ok) {
            const hintData = (await hintRes.json()) as {
              hints?: { severity: string; message: string }[];
            };
            const hints = Array.isArray(hintData.hints) ? hintData.hints : [];
            setRxHints(hints);
            setHintsChecked(true);
            if (hints.length > 0) {
              return;
            }
          } else {
            setHintsChecked(true);
          }
        } catch {
          setHintsChecked(true);
        } finally {
          setCheckingHints(false);
        }
      }

      setSigning(true);
      setWriteError(null);
      try {
        const clinical = mergeInvestigations(draft, selectedDiagnosticLabels);
        const response = await apiFetch("/api/v1/prescription/write", {
          method: "POST",
          body: JSON.stringify({
            raw_identifier: rawIdentifier.trim(),
            doctor_name: doctorName.trim(),
            transcript_count: signTranscriptCount,
            transcripts: transcripts.map((t) => t.text),
            clinical,
            parsed_clinical: parsedClinical,
            source_language: sourceLanguage,
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
        setRxHints([]);
        setHintsChecked(false);
        bumpHistory();
        setStep("share");
      } catch (err) {
        setWriteError(
          err instanceof Error ? err.message : "Could not sign prescription.",
        );
      } finally {
        setSigning(false);
      }
    },
    [
      bumpHistory,
      doctorName,
      draft,
      hintsChecked,
      locked,
      parsedClinical,
      rawIdentifier,
      selectedDiagnosticLabels,
      signTranscriptCount,
      sourceLanguage,
      transcripts,
    ],
  );

  const updateDraftMeds = (medications: MedicationDraft[]) => {
    setDraft((prev) => (prev ? { ...prev, medications } : prev));
    setHintsChecked(false);
    setRxHints([]);
  };

  const showClear =
    transcripts.length > 0 ||
    draftHasContent(textForm) ||
    !!draft ||
    !!pdfBase64 ||
    !!downloadUrl;

  const canShare = !!(pdfBase64 || downloadUrl);

  return (
    <div className="mx-auto w-full max-w-md space-y-6 overflow-x-hidden">
      {!locked ? (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Select a patient at the top before recording or writing a
          prescription.
        </p>
      ) : null}

      <CollapsibleSection
        aria-label={t("prescriptionSection")}
        headerActions={
          showClear ? (
            <button
              className="min-h-11 rounded-lg px-3 text-sm text-slate-600 active:text-slate-900"
              onClick={clearSession}
              type="button"
            >
              {t("clear")}
            </button>
          ) : null
        }
        hint={t("prescriptionHint")}
        title={t("prescriptionSection")}
      >
        <StepTabs
          canReview={!!draft}
          canShare={canShare}
          labels={{
            capture: t("rxStepCapture"),
            review: t("rxStepReview"),
            share: t("rxStepShare"),
          }}
          onSelect={setStep}
          step={step}
        />

        {step === "capture" ? (
          <div className="space-y-4">
            <div
              aria-label={t("prescriptionMode")}
              className="flex rounded-lg border border-slate-200 bg-slate-100 p-1"
              role="tablist"
            >
              {(["voice", "text"] as const).map((m) => {
                const active = mode === m;
                return (
                  <button
                    aria-selected={active}
                    className={`min-h-11 flex-1 rounded-md text-sm font-medium transition-colors ${
                      active
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                    key={m}
                    onClick={() => setMode(m)}
                    role="tab"
                    type="button"
                  >
                    {m === "voice" ? t("rxModeVoice") : t("rxModeText")}
                  </button>
                );
              })}
            </div>

            {mode === "voice" ? (
              <div className="space-y-4">
                <VoiceRecorder
                  disabled={!locked}
                  embedded
                  onTranscript={onTranscript}
                />

                <div>
                  <button
                    className="text-xs font-medium uppercase tracking-wide text-slate-500"
                    onClick={() => setDemoOpen((v) => !v)}
                    type="button"
                  >
                    {demoOpen ? t("hideDemoScripts") : t("demoScripts")}
                  </button>
                  {demoOpen ? (
                    <select
                      className={`${FIELD} mt-2`}
                      disabled={!locked}
                      defaultValue=""
                      onChange={(e) => {
                        const id = e.target.value;
                        e.target.value = "";
                        const script = demoScripts.find((s) => s.id === id);
                        if (!script) return;
                        setTranscripts((prev) => [
                          ...prev,
                          {
                            id: `${Date.now()}-demo`,
                            text: script.text,
                            at: Date.now(),
                          },
                        ]);
                        setWriteError(null);
                      }}
                    >
                      <option value="">{t("loadDemoTranscript")}</option>
                      {demoScripts.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    {t("voiceNotes")} ({transcripts.length})
                  </p>
                  {transcripts.length === 0 ? (
                    <p className="text-sm text-slate-400">
                      No voice notes yet.
                    </p>
                  ) : (
                    <ol className="space-y-2">
                      {transcripts.map((item, index) => (
                        <li
                          key={item.id}
                          className="rounded-lg border border-slate-200 bg-white px-3 py-3"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-xs uppercase tracking-wide text-slate-500">
                              Note {index + 1}
                            </p>
                            <button
                              className="min-h-11 min-w-11 text-xs text-red-600"
                              onClick={() => removeTranscript(item.id)}
                              type="button"
                            >
                              {t("remove")}
                            </button>
                          </div>
                          <p className="mt-1 break-words text-sm text-slate-900">
                            {item.text}
                          </p>
                        </li>
                      ))}
                    </ol>
                  )}
                  <button
                    className="inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
                    disabled={!locked || parsing || transcripts.length === 0}
                    onClick={() => void parseForReview()}
                    type="button"
                  >
                    {parsing ? t("preparing") : t("rxStepReview")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <label className={LABEL}>
                  Diagnoses (one per line)
                  <textarea
                    className={`${AREA} min-h-20`}
                    disabled={!locked}
                    onChange={(e) =>
                      setTextForm((f) => ({
                        ...f,
                        diagnoses: textToLines(e.target.value),
                      }))
                    }
                    value={linesToText(textForm.diagnoses)}
                  />
                </label>
                <label className={LABEL}>
                  Symptoms (one per line)
                  <textarea
                    className={AREA}
                    disabled={!locked}
                    onChange={(e) =>
                      setTextForm((f) => ({
                        ...f,
                        symptoms: textToLines(e.target.value),
                      }))
                    }
                    value={linesToText(textForm.symptoms)}
                  />
                </label>
                <label className={LABEL}>
                  Clinical observations (one per line)
                  <textarea
                    className={AREA}
                    disabled={!locked}
                    onChange={(e) =>
                      setTextForm((f) => ({
                        ...f,
                        clinical_observations: textToLines(e.target.value),
                      }))
                    }
                    value={linesToText(textForm.clinical_observations)}
                  />
                </label>
                <MedicationsEditor
                  disabled={!locked}
                  medications={textForm.medications}
                  onChange={(medications) =>
                    setTextForm((f) => ({ ...f, medications }))
                  }
                />
                <button
                  className="inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
                  disabled={!locked || !draftHasContent(textForm)}
                  onClick={textToReview}
                  type="button"
                >
                  {t("rxStepReview")}
                </button>
              </div>
            )}
          </div>
        ) : null}

        {step === "review" && draft ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Check and edit the details below, then sign to create the
              prescription PDF.
            </p>
            <label className={LABEL}>
              Doctor name on Rx
              <input
                className={FIELD}
                onChange={(e) => setDoctorName(e.target.value)}
                value={doctorName}
              />
            </label>
            <label className={LABEL}>
              Diagnoses (one per line)
              <textarea
                className={`${AREA} min-h-20`}
                onChange={(e) =>
                  setDraft((d) =>
                    d ? { ...d, diagnoses: textToLines(e.target.value) } : d,
                  )
                }
                value={linesToText(draft.diagnoses)}
              />
            </label>
            <label className={LABEL}>
              Symptoms (one per line)
              <textarea
                className={AREA}
                onChange={(e) =>
                  setDraft((d) =>
                    d ? { ...d, symptoms: textToLines(e.target.value) } : d,
                  )
                }
                value={linesToText(draft.symptoms)}
              />
            </label>
            <label className={LABEL}>
              Clinical observations (one per line)
              <textarea
                className={AREA}
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
            <MedicationsEditor
              medications={draft.medications}
              onChange={updateDraftMeds}
            />

            {rxHints.length > 0 ? (
              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
                  Prescription hints
                </p>
                <ul className="space-y-1">
                  {rxHints.map((h) => (
                    <li
                      className={`text-xs ${
                        h.severity === "critical"
                          ? "text-red-700"
                          : "text-amber-900"
                      }`}
                      key={h.message}
                    >
                      {h.message}
                    </li>
                  ))}
                </ul>
                <p className="text-[10px] text-amber-800/80">
                  Decision support only — review, then sign if appropriate.
                </p>
              </div>
            ) : null}

            <button
              className="inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
              disabled={signing || checkingHints}
              onClick={() =>
                void signPrescription(
                  rxHints.length > 0 && hintsChecked
                    ? { skipHints: true }
                    : undefined,
                )
              }
              type="button"
            >
              {checkingHints
                ? t("rxHintsChecking")
                : signing
                  ? t("signing")
                  : rxHints.length > 0 && hintsChecked
                    ? t("signAnyway")
                    : t("signPrescription")}
            </button>
          </div>
        ) : null}

        {step === "share" && canShare ? (
          <PrescriptionShare
            doctorName={doctorName.trim() || "Clinic"}
            downloadUrl={downloadUrl}
            embedded
            patientPhone={patientPhone}
            pdfBase64={pdfBase64}
          />
        ) : null}

        {writeError ? (
          <p className="break-words text-sm text-red-600" role="alert">
            {writeError}
          </p>
        ) : null}
      </CollapsibleSection>
    </div>
  );
}
