"use client";

import { useCallback, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { apiFetch } from "@/lib/doctorSession";
import { printAttachmentBlob } from "@/lib/fileActions";

type Props = {
  /** Optional PDF as base64; when omitted, only the URL mint path is unused. */
  pdfBase64?: string | null;
  doctorName?: string;
  /** If you already have a minted URL, pass it directly. */
  downloadUrl?: string | null;
  /** Clear-text patient phone digits (memory only) for SMS deep-link. */
  patientPhone?: string | null;
  /** Flat light UI for Prescription wizard Share step. */
  embedded?: boolean;
};

function canUseNativeShare(): boolean {
  if (typeof navigator === "undefined") return false;
  return typeof navigator.share === "function";
}

function smsHref(phoneDigits: string, body: string): string {
  let digits = phoneDigits.replace(/\D+/g, "");
  // Indian 10-digit mobiles → E.164 for SMS apps.
  if (digits.length === 10) {
    digits = `91${digits}`;
  }
  const encoded = encodeURIComponent(body);
  return `sms:+${digits}?body=${encoded}`;
}

async function mintDownloadUrl(pdfBase64: string): Promise<string> {
  const response = await apiFetch("/api/v1/prescription/share-link", {
    method: "POST",
    body: JSON.stringify({ pdf_base64: pdfBase64 }),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `Could not create share link (${response.status})`);
  }
  const data = (await response.json()) as { download_url?: string };
  if (!data.download_url) {
    throw new Error("Could not create the share link. Please try again.");
  }
  return data.download_url;
}

export default function PrescriptionShare({
  pdfBase64 = null,
  doctorName = "Clinic",
  downloadUrl = null,
  patientPhone = null,
  embedded = false,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // Defer Web Share detection until after mount so SSR HTML matches the
  // first client render (avoids hydration mismatch when navigator.share exists).
  const [nativeShare, setNativeShare] = useState(false);

  useEffect(() => {
    setNativeShare(canUseNativeShare());
  }, []);

  const resolveUrl = useCallback(async (): Promise<string> => {
    if (downloadUrl?.trim()) return downloadUrl.trim();
    if (!pdfBase64?.trim()) {
      throw new Error("No prescription PDF available to share yet.");
    }
    return mintDownloadUrl(pdfBase64.trim());
  }, [downloadUrl, pdfBase64]);

  const buildMessage = useCallback(
    (url: string) =>
      `Your prescription from Dr. ${doctorName}: ${url}\n\nThis link works for 24 hours.`,
    [doctorName],
  );

  const onNativeShare = useCallback(async () => {
    setBusy(true);
    setStatus(null);
    setCopied(false);
    try {
      const url = await resolveUrl();
      const text = buildMessage(url);
      await navigator.share({
        title: "Secure prescription",
        text,
        url,
      });
      setStatus(
        "Shared. Pick Messages or another app to send it.",
      );
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "AbortError") {
        setStatus("Share cancelled.");
      } else {
        setStatus(
          err instanceof Error
            ? err.message
            : "Could not open share. Please try again.",
        );
      }
    } finally {
      setBusy(false);
    }
  }, [buildMessage, resolveUrl]);

  const onSmsPatient = useCallback(async () => {
    if (!patientPhone?.trim()) {
      setStatus("No mobile number for this patient.");
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const url = await resolveUrl();
      const text = buildMessage(url);
      window.location.href = smsHref(patientPhone, text);
      setStatus("Opening SMS to the patient number…");
    } catch (err) {
      setStatus(
        err instanceof Error ? err.message : "Could not prepare SMS.",
      );
    } finally {
      setBusy(false);
    }
  }, [buildMessage, patientPhone, resolveUrl]);

  const onCopyLink = useCallback(async () => {
    setBusy(true);
    setStatus(null);
    setCopied(false);
    try {
      const url = await resolveUrl();
      const text = buildMessage(url);
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      setStatus("Message copied. Paste it into SMS or any messenger.");
    } catch (err) {
      setStatus(
        err instanceof Error
          ? err.message
          : "Could not copy the prescription link.",
      );
    } finally {
      setBusy(false);
    }
  }, [buildMessage, resolveUrl]);

  const onPrint = useCallback(async () => {
    setBusy(true);
    setStatus(null);
    try {
      let b64 = pdfBase64?.trim() || "";
      if (!b64 && downloadUrl?.trim()) {
        const res = await fetch(downloadUrl.trim());
        if (!res.ok) throw new Error("Could not download PDF for print.");
        const blob = await res.blob();
        await printAttachmentBlob(blob, "prescription.pdf");
        setStatus("Print dialog opened.");
        return;
      }
      if (!b64) throw new Error("No prescription PDF available yet.");
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: "application/pdf" });
      await printAttachmentBlob(blob, "prescription.pdf");
      setStatus("Print dialog opened.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Print failed.");
    } finally {
      setBusy(false);
    }
  }, [downloadUrl, pdfBase64]);

  const secondaryBtn = embedded
    ? "inline-flex min-h-12 min-w-[48px] items-center justify-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-800 transition active:bg-slate-50 disabled:opacity-60"
    : "inline-flex min-h-12 min-w-[48px] items-center justify-center rounded-lg border border-clinical-100/25 bg-black/20 px-4 text-sm font-medium text-clinical-50 transition active:bg-clinical-900 disabled:opacity-60";

  const actions = (
    <>
      <div className="flex flex-col gap-3">
        <button
          className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-semibold text-white disabled:opacity-60"
          disabled={busy}
          onClick={() => void onPrint()}
          type="button"
        >
          {busy ? "Preparing…" : "Print prescription"}
        </button>

        {patientPhone ? (
          <button
            className={secondaryBtn}
            disabled={busy}
            onClick={() => void onSmsPatient()}
            type="button"
          >
            {busy ? "Preparing…" : `SMS to ${patientPhone}`}
          </button>
        ) : null}

        {nativeShare ? (
          <button
            className={secondaryBtn}
            disabled={busy}
            onClick={() => void onNativeShare()}
            type="button"
          >
            {busy ? "Preparing…" : "Share via phone"}
          </button>
        ) : null}

        <button
          className={secondaryBtn}
          disabled={busy}
          onClick={() => void onCopyLink()}
          type="button"
        >
          {copied ? "Copied" : "Copy message link"}
        </button>
      </div>

      {status ? (
        <p
          className={`mt-4 text-sm ${embedded ? "text-slate-700" : "text-clinical-100/80"}`}
          role="status"
        >
          {status}
        </p>
      ) : null}
    </>
  );

  if (embedded) {
    return (
      <div aria-label="Share prescription" className="space-y-3">
        <p className="text-sm text-slate-600">
          Print for the counter first, then share by SMS if needed.
        </p>
        {actions}
      </div>
    );
  }

  return (
    <CollapsibleSection
      aria-label="Share prescription"
      hint="Print for the counter first, then share by SMS if needed."
      title="Prescription ready"
      variant="dark"
    >
      {actions}
    </CollapsibleSection>
  );
}
