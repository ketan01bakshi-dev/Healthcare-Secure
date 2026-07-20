/** Parse API datetimes — SQLite often returns naive UTC without a Z suffix. */
export function parseApiDate(iso: string): Date {
  const trimmed = iso.trim();
  if (!trimmed) return new Date(Number.NaN);
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  return new Date(hasZone ? trimmed : `${trimmed}Z`);
}

/** Format an API ISO timestamp in India Standard Time. */
export function formatIst(iso: string | null | undefined): string {
  if (!iso) return "Date unavailable";
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return "Date unavailable";
  return (
    d.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }) + " IST"
  );
}
