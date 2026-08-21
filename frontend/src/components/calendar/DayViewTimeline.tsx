"use client";

import { useMemo } from "react";

import CalendarEventCard from "@/components/calendar/CalendarEventCard";
import type { AppointmentRow } from "@/lib/appointmentGroups";
import { isSameIstDay } from "@/lib/datetimeIst";
import { useI18n } from "@/lib/i18n";

type Props = {
  items: AppointmentRow[];
  date: Date;
  loading?: boolean;
};

export default function DayViewTimeline({ items, date, loading }: Props) {
  const { t } = useI18n();

  const dayItems = useMemo(
    () =>
      items
        .filter((r) => isSameIstDay(r.scheduled_at, date))
        .sort((a, b) => {
          const ta = new Date(a.scheduled_at!).getTime();
          const tb = new Date(b.scheduled_at!).getTime();
          return ta - tb;
        }),
    [items, date],
  );

  const label = date.toLocaleDateString("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  if (loading) {
    return <p className="text-sm text-slate-500">{t("loadingAppointments")}</p>;
  }

  return (
    <div>
      <p className="mb-4 text-sm font-medium text-slate-600 dark:text-slate-400">
        {label}
      </p>
      {dayItems.length === 0 ? (
        <p className="text-sm text-slate-500">{t("noAppointmentsDay")}</p>
      ) : (
        dayItems.map((item) => <CalendarEventCard item={item} key={item.id} />)
      )}
    </div>
  );
}
