/** Google Calendar template URL + ICS download helpers (IST-aware). */

import { parseApiDate } from "@/lib/datetimeIst";

const IST_OFFSET = "+0530";

export type CalendarEventInput = {
  title: string;
  startIso: string;
  durationMinutes?: number;
  description?: string;
  location?: string;
};

function toUtcDate(iso: string): Date {
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) {
    return new Date(iso);
  }
  return d;
}

/** Google Calendar compact UTC: YYYYMMDDTHHMMSSZ */
function gcalUtcStamp(d: Date): string {
  return d
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}/, "");
}

/** ICS local floating with Z (UTC). */
function icsUtcStamp(d: Date): string {
  return gcalUtcStamp(d);
}

export function googleCalendarUrl(ev: CalendarEventInput): string {
  const start = toUtcDate(ev.startIso);
  const mins = ev.durationMinutes ?? 15;
  const end = new Date(start.getTime() + mins * 60 * 1000);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: ev.title,
    dates: `${gcalUtcStamp(start)}/${gcalUtcStamp(end)}`,
  });
  if (ev.description) params.set("details", ev.description);
  if (ev.location) params.set("location", ev.location);
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function buildIcs(ev: CalendarEventInput): string {
  const start = toUtcDate(ev.startIso);
  const mins = ev.durationMinutes ?? 15;
  const end = new Date(start.getTime() + mins * 60 * 1000);
  const uid = `${start.getTime()}-${Math.random().toString(36).slice(2, 8)}@healthcare-secure`;
  const escape = (s: string) =>
    s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Aarogya One Connect//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTAMP:${icsUtcStamp(new Date())}`,
    `DTSTART:${icsUtcStamp(start)}`,
    `DTEND:${icsUtcStamp(end)}`,
    `SUMMARY:${escape(ev.title)}`,
  ];
  if (ev.description) lines.push(`DESCRIPTION:${escape(ev.description)}`);
  if (ev.location) lines.push(`LOCATION:${escape(ev.location)}`);
  lines.push("END:VEVENT", "END:VCALENDAR");
  return lines.join("\r\n");
}

export function downloadIcs(ev: CalendarEventInput, filename = "appointment.ics") {
  const blob = new Blob([buildIcs(ev)], {
    type: "text/calendar;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function openGoogleCalendar(ev: CalendarEventInput) {
  window.open(googleCalendarUrl(ev), "_blank", "noopener,noreferrer");
}

/** Unused but documents IST offset for future floating local ICS if needed. */
export const _IST_OFFSET = IST_OFFSET;
