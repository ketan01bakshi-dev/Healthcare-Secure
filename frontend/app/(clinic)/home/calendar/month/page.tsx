"use client";

import MonthViewGrid from "@/components/calendar/MonthViewGrid";
import HomeShell from "@/components/home/HomeShell";
import { useAppointments } from "@/hooks/useAppointments";
import { useI18n } from "@/lib/i18n";

export default function CalendarMonthPage() {
  const { t } = useI18n();
  const month = new Date();
  const { items } = useAppointments({ status: "booked" });

  return (
    <HomeShell showFab title={t("viewMonth")}>
      <MonthViewGrid items={items} month={month} />
    </HomeShell>
  );
}
