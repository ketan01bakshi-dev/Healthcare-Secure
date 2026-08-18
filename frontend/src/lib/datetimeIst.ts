/** Parse API datetimes — SQLite often returns naive UTC without a Z suffix. */
export function parseApiDate(iso: string): Date {
  const trimmed = iso.trim();
  if (!trimmed) return new Date(Number.NaN);
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  return new Date(hasZone ? trimmed : `${trimmed}Z`);
}

const IST = "Asia/Kolkata";

/** Format an API ISO timestamp in India Standard Time. */
export function formatIst(iso: string | null | undefined): string {
  if (!iso) return "Date unavailable";
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return "Date unavailable";
  return (
    d.toLocaleString("en-IN", {
      timeZone: IST,
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }) + " IST"
  );
}

/** Short IST time for waiting-list rows (e.g. 09:30 am). */
export function formatIstTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-IN", {
    timeZone: IST,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/** Calendar date parts for a Date in Asia/Kolkata. */
function istYmd(d: Date): { y: number; m: number; day: number } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: IST,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const get = (type: string) =>
    Number(parts.find((p) => p.type === type)?.value || "0");
  return { y: get("year"), m: get("month"), day: get("day") };
}

/**
 * Start/end of "today" in Asia/Kolkata, returned as UTC ISO strings
 * for appointment range queries.
 */
export function istDayBoundsIso(now: Date = new Date()): {
  from: string;
  to: string;
} {
  const { y, m, day } = istYmd(now);
  // IST = UTC+5:30 — construct UTC instants for local midnight / end-of-day
  const startUtcMs =
    Date.UTC(y, m - 1, day, 0, 0, 0, 0) - (5 * 60 + 30) * 60 * 1000;
  const endUtcMs =
    Date.UTC(y, m - 1, day, 23, 59, 59, 999) - (5 * 60 + 30) * 60 * 1000;
  return {
    from: new Date(startUtcMs).toISOString(),
    to: new Date(endUtcMs).toISOString(),
  };
}

/** True if the ISO timestamp falls on the same IST calendar day as `day`. */
export function isSameIstDay(
  iso: string | null | undefined,
  day: Date = new Date(),
): boolean {
  if (!iso) return false;
  const at = parseApiDate(iso);
  if (Number.isNaN(at.getTime())) return false;
  const a = istYmd(at);
  const b = istYmd(day);
  return a.y === b.y && a.m === b.m && a.day === b.day;
}
