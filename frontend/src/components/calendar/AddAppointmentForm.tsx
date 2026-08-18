"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useClinicFeatures } from "@/components/DoctorGate";
import { useNotifications } from "@/context/NotificationContext";
import { notifyAppointmentsChanged } from "@/hooks/useAppointments";
import { formatIst } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

const INPUT =
  "mt-1 min-h-12 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100";

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "");
}

function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AddAppointmentForm() {
  const { t } = useI18n();
  const router = useRouter();
  const { has } = useClinicFeatures();
  const { push: pushNotification } = useNotifications();

  const now = new Date();
  const defaultEnd = new Date(now.getTime() + 30 * 60 * 1000);

  const [title, setTitle] = useState("");
  const [allDay, setAllDay] = useState(false);
  const [start, setStart] = useState(toLocalInputValue(now));
  const [end, setEnd] = useState(toLocalInputValue(defaultEnd));
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [mrn, setMrn] = useState("");
  const [video, setVideo] = useState(false);
  const [notes, setNotes] = useState("");
  const [reminderMins, setReminderMins] = useState<number[]>([30]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const displayName = name.trim();
      const digits = digitsOnly(phone);
      const clinicMrn = mrn.trim();
      if (!displayName) throw new Error(t("nameRequired"));
      if (digits.length !== 10 && !clinicMrn) {
        throw new Error(t("mobileOrMrnRequired"));
      }
      if (!start) throw new Error(t("appointmentWhenRequired"));

      const startDate = new Date(start);
      const endDate = new Date(end);
      let duration = Math.round(
        (endDate.getTime() - startDate.getTime()) / 60000,
      );
      if (allDay) duration = 1440;
      if (duration < 5) duration = 30;

      const modality =
        has("video_consult") && video ? "video" : "in_person";
      const rawIdentifier = clinicMrn
        ? `mrn|${clinicMrn}`
        : `${displayName}|${digits}`;

      const res = await apiFetch("/api/v1/appointments", {
        method: "POST",
        body: JSON.stringify({
          display_name: displayName,
          raw_identifier: rawIdentifier,
          phone: digits.length === 10 ? digits : "",
          clinic_mrn: clinicMrn,
          scheduled_at: startDate.toISOString(),
          duration_minutes: duration,
          reason: title.trim() || "Appointment",
          notes: notes.trim(),
          modality,
          send_sms: true,
        }),
      });
      if (!res.ok) {
        throw new Error((await res.text()).slice(0, 240));
      }
      notifyAppointmentsChanged();
      pushNotification({
        title: t("notifAppointmentAdded"),
        body: `${displayName} · ${formatIst(startDate.toISOString())}`,
        href: "/home/calendar/",
      });
      router.replace("/home/calendar/");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("bookFailed"));
    } finally {
      setBusy(false);
    }
  }

  function removeReminder(mins: number) {
    setReminderMins((prev) => prev.filter((m) => m !== mins));
  }

  return (
    <form className="space-y-1" onSubmit={onSave}>
      <div className="mb-4 flex items-center justify-between">
        <button
          className="min-h-12 px-2 text-slate-600"
          onClick={() => router.back()}
          type="button"
        >
          ✕
        </button>
        <button
          className="rounded-full bg-teal-600 px-6 py-2 text-sm font-semibold text-white disabled:opacity-50"
          disabled={busy}
          type="submit"
        >
          {t("save")}
        </button>
      </div>

      <input
        className="mb-4 w-full border-0 border-b border-slate-200 bg-transparent py-3 text-lg font-medium outline-none dark:border-slate-700"
        onChange={(e) => setTitle(e.target.value)}
        placeholder={t("addTitle")}
        value={title}
      />

      <Row icon="🕐" label={t("allDay")}>
        <input
          checked={allDay}
          className="h-5 w-5"
          onChange={(e) => setAllDay(e.target.checked)}
          type="checkbox"
        />
      </Row>

      <Row icon="▶" label={t("startTime")}>
        <input
          className="w-full border-0 bg-transparent text-sm outline-none dark:text-slate-200"
          onChange={(e) => setStart(e.target.value)}
          type={allDay ? "date" : "datetime-local"}
          value={allDay ? start.slice(0, 10) : start}
        />
      </Row>

      <Row icon="■" label={t("endTime")}>
        <input
          className="w-full border-0 bg-transparent text-sm outline-none dark:text-slate-200"
          onChange={(e) => setEnd(e.target.value)}
          type={allDay ? "date" : "datetime-local"}
          value={allDay ? end.slice(0, 10) : end}
        />
      </Row>

      <Row icon="👤" label={t("addPatient")}>
        <div className="w-full space-y-2">
          <input
            className={INPUT}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("name")}
            required
            value={name}
          />
          <input
            className={INPUT}
            inputMode="numeric"
            onChange={(e) => setPhone(e.target.value)}
            placeholder={t("mobileOrMrnPlaceholder")}
            value={phone}
          />
          <input
            className={INPUT}
            onChange={(e) => setMrn(e.target.value)}
            placeholder={t("appointmentMrnPlaceholder")}
            value={mrn}
          />
        </div>
      </Row>

      {has("video_consult") ? (
        <Row icon="📹" label={t("addVideo")}>
          <input
            checked={video}
            className="h-5 w-5"
            onChange={(e) => setVideo(e.target.checked)}
            type="checkbox"
          />
        </Row>
      ) : null}

      <Row icon="🔔" label={t("notifications")}>
        <div className="flex flex-wrap gap-2">
          {reminderMins.map((m) => (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs dark:bg-slate-800"
              key={m}
            >
              {m} min {t("before")}
              <button
                onClick={() => removeReminder(m)}
                type="button"
              >
                ×
              </button>
            </span>
          ))}
          {!reminderMins.includes(30) ? (
            <button
              className="text-xs text-teal-700"
              onClick={() => setReminderMins((p) => [...p, 30])}
              type="button"
            >
              {t("addNotification")}
            </button>
          ) : null}
        </div>
      </Row>

      <Row icon="≡" label={t("addDescription")}>
        <textarea
          className={`${INPUT} min-h-[4rem]`}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={t("addDescription")}
          value={notes}
        />
      </Row>

      {error ? (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}

function Row({
  icon,
  label,
  children,
}: {
  icon: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3 border-b border-slate-100 py-4 dark:border-slate-800">
      <span className="w-6 shrink-0 text-center text-lg">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <div className="mt-1">{children}</div>
      </div>
    </div>
  );
}
