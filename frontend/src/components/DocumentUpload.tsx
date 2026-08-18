"use client";

import { FormEvent, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import PatientAttachments from "@/components/PatientAttachments";
import { apiFetch } from "@/lib/doctorSession";
import { usePatient } from "@/context/PatientContext";

type Props = {
  onUploaded?: () => void;
  /** Lab users: only diagnostic reports. */
  labOnly?: boolean;
};

export default function DocumentUpload({ onUploaded, labOnly = false }: Props) {
  const { locked, rawIdentifier, bumpHistory } = usePatient();
  const [kind, setKind] = useState<
    "scanned_prescription" | "diagnostic_report" | "other"
  >(labOnly ? "diagnostic_report" : "scanned_prescription");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!locked || !rawIdentifier.trim()) {
      setStatus("Select a patient first.");
      return;
    }
    if (!file) {
      setStatus("Choose a PDF or image file.");
      return;
    }

    setBusy(true);
    setStatus(null);
    try {
      const form = new FormData();
      form.append("raw_identifier", rawIdentifier.trim());
      form.append("document_kind", kind);
      form.append("title", title.trim());
      form.append("file", file);

      const response = await apiFetch("/api/v1/history/documents", {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Upload failed (${response.status})`);
      }
      setStatus("Document saved to patient history.");
      setFile(null);
      setTitle("");
      bumpHistory();
      onUploaded?.();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <CollapsibleSection
      aria-label="Upload scanned documents"
      hint={
        labOnly
          ? "Upload diagnostic lab reports for this patient. The doctor can open them later."
          : "Attach prior prescriptions or lab/scan reports for this patient."
      }
      title={labOnly ? "Lab reports" : "Scanned reports"}
      variant="dark"
    >
      <form className="flex flex-col gap-3" onSubmit={onSubmit}>
        <label className="text-xs uppercase tracking-wide text-clinical-100/55">
          Document type
          <select
            className="mt-1 min-h-12 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900"
            disabled={!locked || busy || labOnly}
            onChange={(e) =>
              setKind(
                e.target.value as
                  | "scanned_prescription"
                  | "diagnostic_report"
                  | "other",
              )
            }
            value={kind}
          >
            {labOnly ? (
              <option value="diagnostic_report">Diagnostic report</option>
            ) : (
              <>
                <option value="scanned_prescription">Scanned prescription</option>
                <option value="diagnostic_report">Diagnostic report</option>
                <option value="other">Other</option>
              </>
            )}
          </select>
        </label>

        <label className="text-xs uppercase tracking-wide text-clinical-100/55">
          Title (optional)
          <input
            className="mt-1 min-h-12 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900"
            disabled={!locked || busy}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Lab report Mar 2026"
            value={title}
          />
        </label>

        <label className="text-xs uppercase tracking-wide text-clinical-100/55">
          File (PDF / JPEG / PNG)
          <input
            accept="application/pdf,image/jpeg,image/png,image/webp"
            className="mt-1 w-full rounded-lg bg-white text-sm text-slate-900"
            disabled={!locked || busy}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            type="file"
          />
        </label>

        <button
          className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white active:bg-clinical-700 disabled:opacity-60"
          disabled={!locked || busy || !file}
          type="submit"
        >
          {busy ? "Uploading…" : "Upload"}
        </button>
      </form>

      {!locked ? (
        <p className="mt-3 text-sm text-clinical-100/50">
          Select a patient above before uploading.
        </p>
      ) : null}
      {status ? (
        <p className="mt-3 break-words text-sm text-clinical-100/80" role="status">
          {status}
        </p>
      ) : null}

      <PatientAttachments documentsOnly embedded />
    </CollapsibleSection>
  );
}
