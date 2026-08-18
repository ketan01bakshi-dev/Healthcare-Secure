"use client";

import { FormEvent, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import { downloadIcs } from "@/lib/calendarExport";
import { formatIst } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

const INPUT =
  "mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none ring-slate-400 focus:ring-2";

type AppointmentRow = {
  id: string;
  display_name: string;
  phone_last4: string;
  scheduled_at: string | null;
  reason: string;
  modality?: string;
  status: string;
  sms_status: string;
};

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "");
}

function notifyAppointmentsChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("healthcare-appointments-changed"));
  }
}

/** Open the phone SMS app with patient number + confirmation text (no gateway needed). */
function openDeviceSms(digits: string, body: string) {
  const to = digits.length === 10 ? digits : digits;
  const href = `sms:${to}?body=${encodeURIComponent(body)}`;
  window.location.href = href;
}

function confirmationSmsBody(
  displayName: string,
  whenLocal: string,
  reason: string,
  modality: string,
): string {
  const reasonBit = reason ? ` (${reason})` : "";
  const kind = modality === "video" ? "video consult" : "appointment";
  return `Clinic ${kind} for ${displayName} on ${whenLocal}${reasonBit}. Reply to clinic if you need to reschedule.`;
}

function calendarEventFor(
  displayName: string,
  scheduledAt: string,
  reason: string,
  modality: string,
) {
  return {
    title: `Clinic: ${displayName}${modality === "video" ? " (Video)" : ""}`,
    startIso: scheduledAt,
    durationMinutes: 15,
    description:
      reason || (modality === "video" ? "Video consult" : "Clinic appointment"),
  };
}

export default function AppointmentScheduler() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const [when, setWhen] = useState("");
  const [reason, setReason] = useState("");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [mrn, setMrn] = useState("");
  const [videoConsult, setVideoConsult] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  if (role === "lab") return null;

  async function onBook(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const displayName = name.trim();
      const digits = digitsOnly(phone);
      const clinicMrn = mrn.trim();
      if (!displayName) {
        throw new Error(t("nameRequired"));
      }
      if (digits.length !== 10 && !clinicMrn) {
        throw new Error(t("mobileOrMrnRequired"));
      }
      if (digits.length > 0 && digits.length !== 10) {
        throw new Error(t("mobileRequired10"));
      }
      if (!when) {
        throw new Error(t("appointmentWhenRequired"));
      }
      const modality =
        has("video_consult") && videoConsult ? "video" : "in_person";
      const rawIdentifier = clinicMrn
        ? `mrn|${clinicMrn}`
        : `${displayName}|${digits}`;
      const whenIso = new Date(when).toISOString();
      const res = await apiFetch("/api/v1/appointments", {
        method: "POST",
        body: JSON.stringify({
          display_name: displayName,
          raw_identifier: rawIdentifier,
          phone: digits.length === 10 ? digits : "",
          clinic_mrn: clinicMrn,
          scheduled_at: whenIso,
          reason: reason.trim(),
          modality,
          send_sms: true,
        }),
      });
      if (!res.ok) {
        const detail = (await res.text()).slice(0, 240);
        throw new Error(detail || `Request failed (${res.status})`);
      }
      const data = (await res.json()) as AppointmentRow;
      const smsStatus = (data.sms_status || "").toLowerCase();
      const carrierSent =
        smsStatus.startsWith("sent:msg91") ||
        smsStatus.startsWith("sent:twilio");
      const noPhone =
        smsStatus.includes("no_phone") ||
        (smsStatus.startsWith("skipped") && !data.phone_last4);
      const needsDeviceSms =
        !noPhone &&
        data.phone_last4 &&
        (smsStatus.startsWith("skipped") ||
          smsStatus.includes("none") ||
          smsStatus.startsWith("sent:console") ||
          smsStatus === "sent");
      const whenLabel = formatIst(whenIso);
      const smsBody = confirmationSmsBody(
        displayName,
        whenLabel,
        reason.trim(),
        modality,
      );
      if (carrierSent) {
        setStatus(t("bookedWithSms"));
      } else if (noPhone) {
        setStatus(t("bookedNoSms"));
      } else if (needsDeviceSms && digits.length === 10) {
        setStatus(t("bookedOpenSms"));
        openDeviceSms(digits, smsBody);
      } else {
        setStatus(`${t("bookedSmsStatus")}: ${data.sms_status || "n/a"}`);
      }
      if (data.scheduled_at) {
        try {
          const ev = calendarEventFor(
            displayName,
            data.scheduled_at,
            reason.trim(),
            modality,
          );
          downloadIcs(ev, `appt-${displayName.replace(/\s+/g, "-")}.ics`);
        } catch {
          /* ICS download often blocked on mobile WebView — booking still succeeded */
        }
      }
      setName("");
      setPhone("");
      setMrn("");
      setReason("");
      setWhen("");
      setVideoConsult(false);
      notifyAppointmentsChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("bookFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CollapsibleSection hint={t("appointmentsHint")} title={t("appointments")}>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={onBook}>
        <label className="text-xs font-medium text-slate-600">
          {t("name")}
          <input
            className={INPUT}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoComplete="name"
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          {t("mobile")}
          <input
            className={INPUT}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            inputMode="numeric"
            autoComplete="tel"
            placeholder={t("mobileOrMrnPlaceholder")}
          />
        </label>
        <label className="text-xs font-medium text-slate-600 sm:col-span-2">
          {t("appointmentMrn")}
          <input
            className={INPUT}
            value={mrn}
            onChange={(e) => setMrn(e.target.value)}
            autoComplete="off"
            placeholder={t("appointmentMrnPlaceholder")}
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          {t("appointmentWhen")}
          <input
            type="datetime-local"
            className={INPUT}
            value={when}
            onChange={(e) => setWhen(e.target.value)}
            required
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          {t("appointmentReason")}
          <input
            className={INPUT}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        {has("video_consult") ? (
          <label className="sm:col-span-2 flex min-h-11 items-center gap-2 text-sm text-slate-800">
            <input
              checked={videoConsult}
              className="h-4 w-4 rounded border-slate-300"
              onChange={(e) => setVideoConsult(e.target.checked)}
              type="checkbox"
            />
            {t("bookAsVideoConsult")}
          </label>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          className="sm:col-span-2 inline-flex min-h-12 items-center justify-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white disabled:opacity-50"
        >
          {t("bookAppointment")}
        </button>
      </form>
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
