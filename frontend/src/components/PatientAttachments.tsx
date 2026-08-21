"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { apiFetch } from "@/lib/doctorSession";
import { usePatient } from "@/context/PatientContext";
import { formatIst } from "@/lib/datetimeIst";
import { useI18n } from "@/lib/i18n";
import {
  blobToViewerPayload,
  openAttachmentNative,
  printAttachmentBlob,
  shareOrDownloadBlob,
  type ViewerPayload,
} from "@/lib/fileActions";

type EncounterData = {
  type?: string;
  document_kind?: string;
  title?: string;
  filename?: string;
  has_content?: boolean;
  issued_at_display?: string;
  diagnoses?: unknown;
  findings?: { summary?: string; [key: string]: unknown } | null;
};

type HistoryRecord = {
  id: string;
  created_at: string | null;
  encounter_data: EncounterData | null;
};

type AttachmentItem = {
  id: string;
  kind: "prescription" | "document";
  label: string;
  subtitle: string;
  createdAt: string | null;
  issuedDisplay: string | null;
  findingsSummary: string | null;
};

function attachmentLabel(data: EncounterData | null): {
  kind: "prescription" | "document";
  label: string;
  subtitle: string;
} {
  if (data?.type === "document") {
    const kind = (data.document_kind || "document").replace(/_/g, " ");
    return {
      kind: "document",
      label: data.title || data.filename || kind,
      subtitle: kind,
    };
  }
  const dx = Array.isArray(data?.diagnoses)
    ? data.diagnoses.filter((x): x is string => typeof x === "string").slice(0, 2)
    : [];
  return {
    kind: "prescription",
    label: dx.length ? `Rx · ${dx.join(", ")}` : "Prescription PDF",
    subtitle: data?.issued_at_display || "Generated prescription",
  };
}

function AttachmentViewer({
  viewer,
  onClose,
  onShare,
}: {
  viewer: ViewerPayload;
  onClose: () => void;
  onShare: () => void;
}) {
  return (
    <div
      aria-modal
      className="fixed inset-0 z-50 flex flex-col bg-black/90"
      role="dialog"
    >
      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
        <p className="min-w-0 truncate text-sm text-white">{viewer.filename}</p>
        <div className="flex shrink-0 gap-2">
          <button
            className="inline-flex min-h-12 items-center rounded-lg border border-white/25 px-3 text-sm text-white"
            onClick={onShare}
            type="button"
          >
            Share
          </button>
          <button
            className="inline-flex min-h-12 items-center rounded-lg bg-clinical-500 px-3 text-sm font-medium text-white"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>
      </div>
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-3">
        {viewer.kind === "image" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            alt={viewer.filename}
            className="max-h-full max-w-full object-contain"
            src={viewer.url}
          />
        ) : viewer.kind === "pdf" ? (
          <iframe
            className="h-full min-h-[70vh] w-full rounded bg-white"
            src={viewer.url}
            title={viewer.filename}
          />
        ) : (
          <p className="text-sm text-white/80">
            Preview not available. Use Share to open this file.
          </p>
        )}
      </div>
      {viewer.kind === "pdf" ? (
        <p className="border-t border-white/10 px-4 py-3 text-center text-xs text-white/60">
          If the PDF is blank on this device, tap Share and open it with a PDF
          app.
        </p>
      ) : null}
    </div>
  );
}

export default function PatientAttachments({
  documentsOnly = false,
  embedded = false,
}: {
  documentsOnly?: boolean;
  /** Render list only (no section chrome) — e.g. inside Scanned reports. */
  embedded?: boolean;
} = {}) {
  const { t } = useI18n();
  const { locked, rawIdentifier, historyVersion, bumpHistory } = usePatient();
  const [items, setItems] = useState<AttachmentItem[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "empty" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [viewer, setViewer] = useState<ViewerPayload | null>(null);
  const [viewerBlob, setViewerBlob] = useState<Blob | null>(null);

  const closeViewer = useCallback(() => {
    if (viewer?.url) {
      URL.revokeObjectURL(viewer.url);
    }
    setViewer(null);
    setViewerBlob(null);
  }, [viewer]);

  const load = useCallback(async (raw: string) => {
    setStatus("loading");
    setError(null);
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
      const mapped: AttachmentItem[] = (data || [])
        .filter((r) => {
          const t = r.encounter_data?.type;
          if (documentsOnly) return t === "document";
          return t === "document" || t === "prescription" || !t;
        })
        .map((r) => {
          const meta = attachmentLabel(r.encounter_data);
          const issued =
            typeof r.encounter_data?.issued_at_display === "string"
              ? r.encounter_data.issued_at_display
              : null;
          return {
            id: r.id,
            kind: meta.kind,
            label: meta.label,
            subtitle: meta.subtitle,
            createdAt: r.created_at,
            issuedDisplay: issued,
            findingsSummary:
              typeof r.encounter_data?.findings?.summary === "string"
                ? r.encounter_data.findings.summary
                : null,
          };
        });
      setItems(mapped);
      setStatus(mapped.length ? "ready" : "empty");
    } catch (err) {
      setStatus("error");
      setError(
        err instanceof Error ? err.message : "Unable to load attachments.",
      );
    }
  }, [documentsOnly]);

  useEffect(() => {
    if (!locked || !rawIdentifier.trim()) {
      setItems([]);
      setStatus("idle");
      setError(null);
      return;
    }
    void load(rawIdentifier.trim());
  }, [locked, rawIdentifier, historyVersion, load]);

  const fetchAttachmentBlob = useCallback(
    async (item: AttachmentItem): Promise<{ blob: Blob; filename: string }> => {
      const path =
        item.kind === "document"
          ? `/api/v1/history/documents/${item.id}/content`
          : `/api/v1/history/records/${item.id}/pdf`;
      const response = await apiFetch(path, {
        method: "POST",
        body: JSON.stringify({ raw_identifier: rawIdentifier.trim() }),
      });
      if (!response.ok) {
        throw new Error(`Could not fetch file (${response.status})`);
      }
      const blob = await response.blob();
      const filename =
        item.kind === "document"
          ? item.label.replace(/[^\w.\- ]+/g, "_") || "document"
          : `prescription-${item.id.slice(0, 8)}.pdf`;
      return { blob, filename };
    },
    [rawIdentifier],
  );

  const openOrDownload = useCallback(
    async (item: AttachmentItem, mode: "open" | "download" | "print") => {
      if (!rawIdentifier.trim()) return;
      setBusyId(item.id);
      setError(null);
      try {
        const { blob, filename } = await fetchAttachmentBlob(item);
        if (mode === "download") {
          const result = await shareOrDownloadBlob(blob, filename);
          setError(
            result === "shared"
              ? "Choose how to save or share the file."
              : "Download started.",
          );
          return;
        }
        if (mode === "print") {
          await printAttachmentBlob(blob, filename);
          setError("Print dialog opened.");
          return;
        }

        const payload = blobToViewerPayload(blob, filename);
        const isCap =
          !!(window as unknown as { Capacitor?: unknown }).Capacitor;

        if (payload.kind === "pdf" && isCap) {
          URL.revokeObjectURL(payload.url);
          const result = await openAttachmentNative(blob, filename);
          setError(
            result === "opened"
              ? "Opened in your PDF viewer. Use Back to return here."
              : "Choose a PDF app to open the file.",
          );
          return;
        }

        setViewerBlob(blob);
        setViewer(payload);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Download failed.");
      } finally {
        setBusyId(null);
      }
    },
    [fetchAttachmentBlob, rawIdentifier],
  );

  const analyzeDocument = useCallback(
    async (item: AttachmentItem) => {
      if (!rawIdentifier.trim() || item.kind !== "document") return;
      setAnalyzingId(item.id);
      setError(null);
      try {
        const response = await apiFetch(
          `/api/v1/history/documents/${item.id}/analyze`,
          {
            method: "POST",
            body: JSON.stringify({ raw_identifier: rawIdentifier.trim() }),
          },
        );
        if (!response.ok) {
          throw new Error(`Analyze failed (${response.status})`);
        }
        const data = (await response.json()) as {
          findings?: { summary?: string };
        };
        const summary =
          typeof data.findings?.summary === "string"
            ? data.findings.summary
            : null;
        setItems((prev) =>
          prev.map((it) =>
            it.id === item.id ? { ...it, findingsSummary: summary } : it,
          ),
        );
        bumpHistory();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Could not analyze report.",
        );
      } finally {
        setAnalyzingId(null);
      }
    },
    [bumpHistory, rawIdentifier],
  );

  const headerNote = useMemo(() => {
    if (!locked) return "Select a patient to see attachments.";
    if (status === "loading") return "Loading attachments…";
    if (status === "empty") {
      return documentsOnly
        ? "No scanned reports yet."
        : "No prescriptions or reports yet.";
    }
    return documentsOnly
      ? "Open, print, or download reports for this patient."
      : "Open to view, Print to print, or Download to save on your phone.";
  }, [locked, status, documentsOnly]);

  const listBody = (
    <>
      {status === "error" && error ? (
        <p className="text-sm text-red-300" role="alert">
          {error}
        </p>
      ) : null}
      {status !== "error" && error ? (
        <p className="text-sm text-clinical-100/80" role="status">
          {error}
        </p>
      ) : null}

      {embedded && locked && status !== "ready" && status !== "error" ? (
        <p className="text-sm text-clinical-100/55">{headerNote}</p>
      ) : null}

      {status === "ready" ? (
        <ul
          className={
            embedded
              ? "mt-2 divide-y divide-clinical-100/10 border-t border-clinical-100/15"
              : "divide-y divide-clinical-100/10"
          }
        >
          {items.map((item) => (
            <li
              className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
              key={item.id}
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-clinical-50">
                  {item.label}
                </p>
                <p className="mt-0.5 text-xs text-clinical-100/55">
                  {item.issuedDisplay || formatIst(item.createdAt)} ·{" "}
                  {item.subtitle}
                </p>
                {item.findingsSummary ? (
                  <p className="mt-1 text-xs text-clinical-100/80">
                    Findings: {item.findingsSummary}
                  </p>
                ) : null}
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                {item.kind === "document" ? (
                  <button
                    className="inline-flex min-h-12 items-center justify-center rounded-lg border border-teal-300/40 px-3 text-sm text-teal-100 disabled:opacity-60"
                    disabled={busyId === item.id || analyzingId === item.id}
                    onClick={() => void analyzeDocument(item)}
                    type="button"
                  >
                    {analyzingId === item.id ? "Analyzing…" : "Analyze"}
                  </button>
                ) : null}
                <button
                  className="inline-flex min-h-12 items-center justify-center rounded-lg border border-slate-200 px-3 text-sm text-slate-800 disabled:opacity-60"
                  disabled={busyId === item.id}
                  onClick={() => void openOrDownload(item, "open")}
                  type="button"
                >
                  Open
                </button>
                <button
                  className="inline-flex min-h-12 items-center justify-center rounded-lg border border-slate-200 px-3 text-sm text-slate-800 disabled:opacity-60"
                  disabled={busyId === item.id}
                  onClick={() => void openOrDownload(item, "print")}
                  type="button"
                >
                  Print
                </button>
                <button
                  className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-3 text-sm font-medium text-white disabled:opacity-60"
                  disabled={busyId === item.id}
                  onClick={() => void openOrDownload(item, "download")}
                  type="button"
                >
                  {busyId === item.id ? "…" : "Download"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );

  return (
    <>
      {embedded ? (
        <div aria-label="Scanned reports list" className="mt-4">
          {listBody}
        </div>
      ) : (
        <CollapsibleSection
          aria-label="Patient attachments"
          className="mx-auto w-full max-w-3xl rounded-2xl border border-clinical-500/25 bg-clinical-900/70 px-4 py-6 sm:px-6"
          hint={headerNote}
          title={t("attachments")}
          variant="dark"
        >
          {listBody}
        </CollapsibleSection>
      )}

      {viewer ? (
        <AttachmentViewer
          onClose={closeViewer}
          onShare={() => {
            if (!viewerBlob) return;
            void shareOrDownloadBlob(viewerBlob, viewer.filename).catch((err) =>
              setError(err instanceof Error ? err.message : "Share failed."),
            );
          }}
          viewer={viewer}
        />
      ) : null}
    </>
  );
}
