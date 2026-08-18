/** Obstetric dating helpers (Naegele / gestational age). */

import { parseApiDate } from "@/lib/datetimeIst";

export type ObstetricProfile = {
  lmp: string | null;
  edd: string | null;
  edd_source: "lmp" | "usg" | "";
  gravida: string;
  para: string;
  abortions: string;
  living: string;
  blood_group: string;
  rh: string;
  high_risk_notes: string;
};

export const EMPTY_OBSTETRIC: ObstetricProfile = {
  lmp: null,
  edd: null,
  edd_source: "",
  gravida: "",
  para: "",
  abortions: "",
  living: "",
  blood_group: "",
  rh: "",
  high_risk_notes: "",
};

/** Parse YYYY-MM-DD as a calendar date (noon UTC to avoid TZ edge). */
export function parseDateOnly(ymd: string | null | undefined): Date | null {
  if (!ymd || !/^\d{4}-\d{2}-\d{2}$/.test(ymd.trim())) return null;
  const [y, m, d] = ymd.trim().split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
}

/** Naegele: LMP + 280 days. */
export function eddFromLmp(lmpYmd: string): string | null {
  const lmp = parseDateOnly(lmpYmd);
  if (!lmp) return null;
  const edd = new Date(lmp.getTime() + 280 * 24 * 60 * 60 * 1000);
  const y = edd.getUTCFullYear();
  const m = String(edd.getUTCMonth() + 1).padStart(2, "0");
  const d = String(edd.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export type GestationalAge = {
  totalDays: number;
  weeks: number;
  days: number;
  label: string;
  /** Fractional weeks for chart X axis */
  weekFloat: number;
};

/** GA from LMP at a given instant (or today). */
export function gestationalAgeAt(
  lmpYmd: string | null | undefined,
  at: Date | string = new Date(),
): GestationalAge | null {
  const lmp = parseDateOnly(lmpYmd || "");
  if (!lmp) return null;
  const when =
    typeof at === "string" ? parseApiDate(at) : at instanceof Date ? at : new Date();
  if (Number.isNaN(when.getTime())) return null;
  const ms = when.getTime() - lmp.getTime();
  const totalDays = Math.floor(ms / (24 * 60 * 60 * 1000));
  if (totalDays < 0 || totalDays > 314) return null; // > ~45w ignore
  const weeks = Math.floor(totalDays / 7);
  const days = totalDays % 7;
  return {
    totalDays,
    weeks,
    days,
    label: `${weeks}w${days}d`,
    weekFloat: totalDays / 7,
  };
}

export function gplaLabel(p: ObstetricProfile): string {
  const g = p.gravida.trim() || "—";
  const pa = p.para.trim() || "—";
  const a = p.abortions.trim() || "—";
  const l = p.living.trim() || "—";
  return `G${g} P${pa} A${a} L${l}`;
}
