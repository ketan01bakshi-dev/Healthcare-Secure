"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { printAttachmentBlob } from "@/lib/fileActions";
import {
  apiFetch,
  getClinicGate,
  getClinicUser,
} from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

const INPUT =
  "mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none ring-slate-400 focus:ring-2";

type Mode = "external" | "colleague";

type PackResponse = {
  pdf_base64?: string;
  download_url?: string;
  expires_at?: number;
};

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "");
}

function canUseNativeShare(): boolean {
  if (typeof navigator === "undefined") return false;
  return typeof navigator.share === "function";
}

function smsHref(phoneDigits: string, body: string): string {
  let digits = phoneDigits.replace(/\D+/g, "");
  if (digits.length === 10) {
    digits = `91${digits}`;
  }
  return `sms:+${digits}?body=${encodeURIComponent(body)}`;
}

function b64ToBlob(b64: string): Blob {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: "application/pdf" });
}

export default function ForwardCaseHistory() {
  const { t } = useI18n();
  const { locked, rawIdentifier, patientName } = usePatient();
  const [mode, setMode] = useState<Mode>("external");
  const [note, setNote] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [recipientMobile, setRecipientMobile] = useState("");
  const [toUserId, setToUserId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [nativeShare, setNativeShare] = useState(false);

  const me = getClinicUser();
  const colleagues = useMemo(() => {
    const users = getClinicGate()?.users ?? [];
    return users.filter(
      (u) => u.role === "doctor" && u.user_id !== me?.user_id,
    );
  }, [me?.user_id]);

  useEffect(() => {
    setNativeShare(canUseNativeShare());
  }, []);

  useEffect(() => {
    if (colleagues.length && !toUserId) {
      setToUserId(colleagues[0].user_id);
    }
  }, [colleagues, toUserId]);

  const buildMessage = useCallback(
    (url: string) => {
      const who = recipientName.trim() || "Doctor";
      const from = me?.display_name || "Clinic";
      return (
        `Clinical referral for ${who} from Dr. ${from}` +
        (patientName ? ` (patient: ${patientName})` : "") +
        `:\n${url}\n\nLink works for 24 hours. Verify against the chart.`
      );
    },
    [me?.display_name, patientName, recipientName],
  );

  const onGenerate = useCallback(async () => {
    if (!locked || !rawIdentifier) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const res = await apiFetch("/api/v1/history/referral-pack", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          note: note.trim(),
          recipient_name: recipientName.trim(),
          patient_display_name: patientName,
        }),
      });
      if (!res.ok) {
        throw new Error((await res.text()).slice(0, 240) || t("forwardPackFailed"));
      }
      const data = (await res.json()) as PackResponse;
      if (!data.pdf_base64 || !data.download_url) {
        throw new Error(t("forwardPackFailed"));
      }
      setPdfBase64(data.pdf_base64);
      setDownloadUrl(data.download_url);
      setStatus(t("forwardPackReady"));
    } catch (e) {
      setPdfBase64(null);
      setDownloadUrl(null);
      setError(e instanceof Error ? e.message : t("forwardPackFailed"));
    } finally {
      setBusy(false);
    }
  }, [locked, rawIdentifier, note, recipientName, patientName, t]);

  const ensurePack = useCallback(async (): Promise<{
    pdfBase64: string;
    downloadUrl: string;
  }> => {
    if (pdfBase64 && downloadUrl) {
      return { pdfBase64, downloadUrl };
    }
    const res = await apiFetch("/api/v1/history/referral-pack", {
      method: "POST",
      body: JSON.stringify({
        raw_identifier: rawIdentifier,
        note: note.trim(),
        recipient_name: recipientName.trim(),
        patient_display_name: patientName,
      }),
    });
    if (!res.ok) {
      throw new Error((await res.text()).slice(0, 240) || t("forwardPackFailed"));
    }
    const data = (await res.json()) as PackResponse;
    if (!data.pdf_base64 || !data.download_url) {
      throw new Error(t("forwardPackFailed"));
    }
    setPdfBase64(data.pdf_base64);
    setDownloadUrl(data.download_url);
    return { pdfBase64: data.pdf_base64, downloadUrl: data.download_url };
  }, [pdfBase64, downloadUrl, rawIdentifier, note, recipientName, patientName, t]);

  const onPrint = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const pack = await ensurePack();
      await printAttachmentBlob(
        b64ToBlob(pack.pdfBase64),
        `referral-${(patientName || "patient").replace(/\s+/g, "-")}.pdf`,
      );
      setStatus(t("forwardPackReady"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("forwardPackFailed"));
    } finally {
      setBusy(false);
    }
  }, [ensurePack, patientName, t]);

  const onCopy = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const pack = await ensurePack();
      const text = buildMessage(pack.downloadUrl);
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
      setStatus(t("forwardCopyLink"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("forwardPackFailed"));
    } finally {
      setBusy(false);
    }
  }, [buildMessage, ensurePack, t]);

  const onShare = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const pack = await ensurePack();
      const text = buildMessage(pack.downloadUrl);
      if (canUseNativeShare()) {
        await navigator.share({
          title: "Clinical referral",
          text,
          url: pack.downloadUrl,
        });
        setStatus(t("forwardShare"));
      } else {
        await navigator.clipboard?.writeText(text);
        setStatus(t("forwardCopyLink"));
      }
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      if (name === "AbortError") {
        setStatus("Share cancelled.");
      } else {
        setError(e instanceof Error ? e.message : t("forwardPackFailed"));
      }
    } finally {
      setBusy(false);
    }
  }, [buildMessage, ensurePack, t]);

  const onSms = useCallback(async () => {
    const digits = digitsOnly(recipientMobile);
    if (digits.length !== 10) {
      setError(t("forwardMobileRequired"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const pack = await ensurePack();
      window.location.href = smsHref(digits, buildMessage(pack.downloadUrl));
      setStatus(t("forwardSms"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("forwardPackFailed"));
    } finally {
      setBusy(false);
    }
  }, [buildMessage, ensurePack, recipientMobile, t]);

  const onHandoff = useCallback(async () => {
    if (!locked || !rawIdentifier || !toUserId) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const res = await apiFetch("/api/v1/history/referral-handoff", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          to_user_id: toUserId,
          note: note.trim(),
          patient_display_name: patientName,
        }),
      });
      if (!res.ok) {
        throw new Error(
          (await res.text()).slice(0, 240) || t("forwardHandoffFailed"),
        );
      }
      setStatus(t("forwardHandoffOk"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("forwardHandoffFailed"));
    } finally {
      setBusy(false);
    }
  }, [locked, rawIdentifier, toUserId, note, patientName, t]);

  if (!locked) return null;

  const tabBtn = (id: Mode, label: string) => (
    <button
      aria-pressed={mode === id}
      className={`min-h-10 flex-1 rounded-lg px-3 text-sm font-medium ${
        mode === id
          ? "bg-slate-900 text-white"
          : "border border-slate-200 bg-white text-slate-700"
      }`}
      onClick={() => setMode(id)}
      type="button"
    >
      {label}
    </button>
  );

  return (
    <CollapsibleSection
      hint={t("forwardCaseHistoryHint")}
      title={t("forwardCaseHistory")}
    >
      <div className="flex gap-2">
        {tabBtn("external", t("forwardExternal"))}
        {tabBtn("colleague", t("forwardColleague"))}
      </div>

      <label className="mt-3 block text-xs font-medium text-slate-600">
        {t("forwardNote")}
        <textarea
          className={`${INPUT} min-h-20`}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("forwardNotePlaceholder")}
          value={note}
        />
      </label>

      {mode === "external" ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-600">
            {t("forwardRecipientName")}
            <input
              className={INPUT}
              onChange={(e) => setRecipientName(e.target.value)}
              value={recipientName}
            />
          </label>
          <label className="text-xs font-medium text-slate-600">
            {t("forwardRecipientMobile")}
            <input
              className={INPUT}
              inputMode="numeric"
              onChange={(e) => setRecipientMobile(e.target.value)}
              value={recipientMobile}
            />
          </label>
          <div className="sm:col-span-2 flex flex-wrap gap-2">
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white disabled:opacity-50"
              disabled={busy}
              onClick={() => void onGenerate()}
              type="button"
            >
              {t("forwardGenerate")}
            </button>
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 disabled:opacity-50"
              disabled={busy}
              onClick={() => void onPrint()}
              type="button"
            >
              {t("forwardPrint")}
            </button>
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 disabled:opacity-50"
              disabled={busy}
              onClick={() => void onCopy()}
              type="button"
            >
              {t("forwardCopyLink")}
            </button>
            {nativeShare ? (
              <button
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 disabled:opacity-50"
                disabled={busy}
                onClick={() => void onShare()}
                type="button"
              >
                {t("forwardShare")}
              </button>
            ) : null}
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 disabled:opacity-50"
              disabled={busy}
              onClick={() => void onSms()}
              type="button"
            >
              {t("forwardSms")}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          {colleagues.length === 0 ? (
            <p className="text-sm text-amber-800">{t("forwardNoDoctors")}</p>
          ) : (
            <label className="block text-xs font-medium text-slate-600">
              {t("forwardSelectDoctor")}
              <select
                className={INPUT}
                onChange={(e) => setToUserId(e.target.value)}
                value={toUserId}
              >
                {colleagues.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white disabled:opacity-50"
            disabled={busy || !toUserId || colleagues.length === 0}
            onClick={() => void onHandoff()}
            type="button"
          >
            {t("forwardHandoff")}
          </button>
        </div>
      )}

      {error ? (
        <p className="mt-2 text-sm text-amber-800" role="alert">
          {error}
        </p>
      ) : null}
      {status ? (
        <p className="mt-2 text-sm text-emerald-800" role="status">
          {status}
        </p>
      ) : null}
    </CollapsibleSection>
  );
}
