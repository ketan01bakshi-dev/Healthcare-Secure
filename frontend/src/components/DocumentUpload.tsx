"use client";

import { FormEvent, useState } from "react";

import { apiFetch } from "@/lib/doctorSession";
import { usePatient } from "@/context/PatientContext";

type Props = {
  onUploaded?: () => void;
};

export default function DocumentUpload({ onUploaded }: Props) {
  const { locked, rawIdentifier, bumpHistory } = usePatient();
  const [kind, setKind] = useState<
    "scanned_prescription" | "diagnostic_report" | "other"
  >("scanned_prescription");
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
    <section
      aria-label="Upload scanned documents"
      className="mx-auto w-full max-w-md overflow-x-hidden rounded-2xl border border-clinical-100/15 bg-clinical-900/40 px-4 py-6 sm:px-6"
    >
      <h2 className="text-lg font-semibold tracking-tight text-clinical-50">
        Scanned Rx &amp; reports
      </h2>
      <p className="mt-2 text-sm text-clinical-100/70">
        Attach prior prescriptions or lab/scan reports for this patient.
      </p>

      <form className="mt-5 flex flex-col gap-3" onSubmit={onSubmit}>
        <label className="text-xs uppercase tracking-wide text-clinical-100/55">
          Document type
          <select
            className="mt-1 min-h-12 w-full rounded-lg border border-clinical-100/20 bg-black/25 px-3 text-sm text-clinical-50"
            disabled={!locked || busy}
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
            <option value="scanned_prescription">Scanned prescription</option>
            <option value="diagnostic_report">Diagnostic report</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label className="text-xs uppercase tracking-wide text-clinical-100/55">
          Title (optional)
          <input
            className="mt-1 min-h-12 w-full rounded-lg border border-clinical-100/20 bg-black/25 px-3 text-sm text-clinical-50"
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
            className="mt-1 w-full text-sm text-clinical-100"
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
          {busy ? "Uploading…" : "Upload to history"}
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
    </section>
  );
}
