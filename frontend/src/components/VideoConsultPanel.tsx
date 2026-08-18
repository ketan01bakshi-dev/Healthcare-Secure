"use client";

import { useCallback, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { getPrefillDoctorName } from "@/components/DoctorGate";
import { usePatient } from "@/context/PatientContext";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

type SessionPayload = {
  room_name: string;
  join_url: string;
  doctor_url: string;
  doctor_display_name?: string;
  hint?: string;
};

function openDeviceSms(digits: string, body: string) {
  const href = `sms:${digits}?body=${encodeURIComponent(body)}`;
  window.location.href = href;
}

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "");
}

/** Doctor Visit panel — Jitsi embed + SMS/copy join link (no call recording). */
export default function VideoConsultPanel() {
  const { t } = useI18n();
  const { locked, rawIdentifier, patientPhone, bumpHistory } = usePatient();
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [showEmbed, setShowEmbed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startSession = useCallback(async () => {
    if (!rawIdentifier) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const res = await apiFetch("/api/v1/video-consult/session", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          write_timeline: true,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as SessionPayload;
      setSession(data);
      setShowEmbed(true);
      setStatus(t("videoSessionReady"));
      bumpHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("videoSessionFailed"));
    } finally {
      setBusy(false);
    }
  }, [rawIdentifier, bumpHistory, t]);

  async function copyLink() {
    if (!session?.join_url) return;
    try {
      await navigator.clipboard.writeText(session.join_url);
      setStatus(t("videoLinkCopied"));
    } catch {
      setStatus(session.join_url);
    }
  }

  async function smsInvite() {
    if (!session?.join_url || !rawIdentifier) return;
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/video-consult/invite-sms", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          join_url: session.join_url,
        }),
      });
      const digits = digitsOnly(patientPhone || "");
      if (!res.ok) {
        const detail = await res.text();
        if (digits.length === 10) {
          openDeviceSms(
            digits,
            `${t("videoSmsPrefix")} ${session.join_url}`,
          );
          setStatus(t("videoOpenedDeviceSms"));
          return;
        }
        throw new Error(detail);
      }
      const data = (await res.json()) as {
        sms_status?: string;
        provider?: string;
      };
      const smsStatus = (data.sms_status || "").toLowerCase();
      const carrier =
        smsStatus.startsWith("sent") &&
        (smsStatus.includes("msg91") || smsStatus.includes("twilio"));
      if (carrier) {
        setStatus(t("videoSmsSent"));
      } else if (digits.length === 10) {
        openDeviceSms(digits, `${t("videoSmsPrefix")} ${session.join_url}`);
        setStatus(t("videoOpenedDeviceSms"));
      } else {
        setStatus(`${t("videoSmsStatus")}: ${data.sms_status || "n/a"}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("videoSmsFailed"));
    } finally {
      setBusy(false);
    }
  }

  function openInBrowser() {
    if (!session?.doctor_url) return;
    window.open(session.doctor_url, "_blank", "noopener,noreferrer");
  }

  if (!locked) return null;

  const doctorName =
    session?.doctor_display_name || getPrefillDoctorName() || "Doctor";
  const embedSrc = session
    ? `${session.doctor_url}#userInfo.displayName="${encodeURIComponent(doctorName)}"`
    : "";

  return (
    <CollapsibleSection
      hint={t("videoConsultHint")}
      title={t("videoConsult")}
    >
      <p className="text-xs text-slate-600">{t("videoMicConflictHint")}</p>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="inline-flex min-h-11 items-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white disabled:opacity-50"
          disabled={busy}
          onClick={() => void startSession()}
        >
          {busy && !session ? t("videoStarting") : t("videoStart")}
        </button>
        {session ? (
          <>
            <button
              type="button"
              className="inline-flex min-h-11 items-center rounded-lg border border-slate-200 px-4 text-sm text-slate-800 disabled:opacity-50"
              disabled={busy}
              onClick={() => void copyLink()}
            >
              {t("videoCopyLink")}
            </button>
            <button
              type="button"
              className="inline-flex min-h-11 items-center rounded-lg border border-slate-200 px-4 text-sm text-slate-800 disabled:opacity-50"
              disabled={busy}
              onClick={() => void smsInvite()}
            >
              {t("videoSmsInvite")}
            </button>
            <button
              type="button"
              className="inline-flex min-h-11 items-center rounded-lg border border-slate-200 px-4 text-sm text-slate-800"
              onClick={openInBrowser}
            >
              {t("videoOpenBrowser")}
            </button>
            <button
              type="button"
              className="inline-flex min-h-11 items-center rounded-lg border border-slate-200 px-4 text-sm text-slate-800"
              onClick={() => setShowEmbed((v) => !v)}
            >
              {showEmbed ? t("videoHideEmbed") : t("videoShowEmbed")}
            </button>
          </>
        ) : null}
      </div>

      {error ? (
        <p className="text-sm text-amber-800" role="alert">
          {error}
        </p>
      ) : null}
      {status ? (
        <p className="text-sm text-emerald-800" role="status">
          {status}
        </p>
      ) : null}

      {session && showEmbed ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900">
          <iframe
            allow="camera; microphone; display-capture; autoplay; clipboard-write"
            allowFullScreen
            className="aspect-video w-full min-h-[280px] border-0"
            src={embedSrc}
            title={t("videoConsult")}
          />
          <p className="px-3 py-2 text-[11px] text-slate-300">
            {t("videoEmbedFallback")}
          </p>
        </div>
      ) : null}
    </CollapsibleSection>
  );
}
