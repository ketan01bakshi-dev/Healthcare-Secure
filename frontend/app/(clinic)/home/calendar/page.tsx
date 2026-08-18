"use client";

import { useMemo } from "react";

import ScheduleViewList from "@/components/calendar/ScheduleViewList";
import HomeShell from "@/components/home/HomeShell";
import OfflineSyncBanner from "@/components/OfflineSyncBanner";
import { groupAppointmentsByDay } from "@/lib/appointmentGroups";
import { useAppointments } from "@/hooks/useAppointments";
import { useI18n } from "@/lib/i18n";

export default function CalendarSchedulePage() {
  const { t } = useI18n();
  const { items, loading } = useAppointments({ status: "booked" });
  const groups = useMemo(() => groupAppointmentsByDay(items), [items]);
  const monthTitle =
    groups[0]?.monthLabel ||
    new Date().toLocaleDateString("en-IN", {
      timeZone: "Asia/Kolkata",
      month: "long",
      year: "numeric",
    });

  return (
    <HomeShell showFab showNotification title={monthTitle}>
      <OfflineSyncBanner />
      <ScheduleViewList groups={groups} loading={loading} />
      {!loading && groups.length === 0 ? (
        <p className="mt-2 text-center text-xs text-slate-500">
          {t("calendarScheduleHint")}
        </p>
      ) : null}
    </HomeShell>
  );
}
