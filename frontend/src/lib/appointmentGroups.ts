import { parseApiDate } from "@/lib/datetimeIst";

const IST = "Asia/Kolkata";

export type AppointmentRow = {
  id: string;
  display_name: string;
  phone_last4: string;
  scheduled_at: string | null;
  reason: string;
  modality?: string;
  status: string;
  sms_status: string;
  duration_minutes?: number;
  notes?: string;
};

export type AppointmentDayGroup = {
  dayKey: string;
  label: string;
  monthLabel: string;
  items: AppointmentRow[];
};

function istDayKey(iso: string): string {
  const d = parseApiDate(iso);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: IST,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const get = (type: string) =>
    parts.find((p) => p.type === type)?.value || "00";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function formatDayLabel(iso: string): string {
  const d = parseApiDate(iso);
  return d.toLocaleDateString("en-IN", {
    timeZone: IST,
    weekday: "short",
    day: "numeric",
  });
}

function formatMonthLabel(iso: string): string {
  const d = parseApiDate(iso);
  return d.toLocaleDateString("en-IN", {
    timeZone: IST,
    month: "long",
    year: "numeric",
  });
}

/** Group booked appointments by IST calendar day (only days with events). */
export function groupAppointmentsByDay(
  rows: AppointmentRow[],
): AppointmentDayGroup[] {
  const sorted = [...rows]
    .filter((r) => r.scheduled_at)
    .sort((a, b) => {
      const ta = parseApiDate(a.scheduled_at!).getTime();
      const tb = parseApiDate(b.scheduled_at!).getTime();
      return ta - tb;
    });

  const map = new Map<string, AppointmentRow[]>();
  for (const row of sorted) {
    const key = istDayKey(row.scheduled_at!);
    const list = map.get(key) || [];
    list.push(row);
    map.set(key, list);
  }

  return [...map.entries()].map(([dayKey, items]) => ({
    dayKey,
    label: formatDayLabel(items[0].scheduled_at!),
    monthLabel: formatMonthLabel(items[0].scheduled_at!),
    items,
  }));
}
