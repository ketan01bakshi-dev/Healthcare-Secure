"use client";

import Link from "next/link";
import { useMemo } from "react";

import type { AppointmentRow } from "@/lib/appointmentGroups";
import { parseApiDate } from "@/lib/datetimeIst";

const IST = "Asia/Kolkata";
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

type Props = {
  items: AppointmentRow[];
  month: Date;
};

function ymdInIst(d: Date): { y: number; m: number; day: number } {
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

export default function MonthViewGrid({ items, month }: Props) {
  const { y, m } = ymdInIst(month);
  const counts = useMemo(() => {
    const map = new Map<string, number>();
    for (const row of items) {
      if (!row.scheduled_at) continue;
      const { y: yy, m: mm, day } = ymdInIst(parseApiDate(row.scheduled_at));
      const key = `${yy}-${mm}-${day}`;
      map.set(key, (map.get(key) || 0) + 1);
    }
    return map;
  }, [items]);

  const first = new Date(Date.UTC(y, m - 1, 1));
  const startPad = first.getUTCDay();
  const daysInMonth = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const cells: Array<{ day: number | null; key: string }> = [];
  for (let i = 0; i < startPad; i++) cells.push({ day: null, key: `pad-${i}` });
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, key: `${y}-${m}-${d}` });
  }

  const monthLabel = month.toLocaleDateString("en-IN", {
    timeZone: IST,
    month: "long",
    year: "numeric",
  });

  return (
    <div>
      <p className="mb-3 text-center text-sm font-semibold text-slate-800 dark:text-slate-200">
        {monthLabel}
      </p>
      <div className="mb-2 grid grid-cols-7 gap-1 text-center text-[10px] font-medium text-slate-500">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell) => {
          if (cell.day === null) {
            return <div className="aspect-square" key={cell.key} />;
          }
          const count = counts.get(cell.key) || 0;
          const href = `/home/calendar/day/?date=${y}-${String(m).padStart(2, "0")}-${String(cell.day).padStart(2, "0")}`;
          return (
            <Link
              className={`flex aspect-square flex-col items-center justify-center rounded-lg text-sm ${
                count > 0
                  ? "bg-teal-100 font-semibold text-teal-900 dark:bg-teal-900/50 dark:text-teal-100"
                  : "text-slate-700 dark:text-slate-300"
              }`}
              href={href}
              key={cell.key}
            >
              {cell.day}
              {count > 0 ? (
                <span className="text-[9px] font-normal">{count} appt</span>
              ) : null}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
