"use client";

import DayViewTimeline from "@/components/calendar/DayViewTimeline";
import HomeShell from "@/components/home/HomeShell";
import { useAppointments } from "@/hooks/useAppointments";
import { useI18n } from "@/lib/i18n";
import { useSearchParams } from "next/navigation";

function parseDateParam(raw: string | null): Date {
  if (!raw) return new Date();
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  if (!m) return new Date();
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
}

export default function CalendarDayPage() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const date = parseDateParam(searchParams.get("date"));

  const { items, loading } = useAppointments({ status: "booked" });

  return (
    <HomeShell showFab showNotification title={t("viewDay")}>
      <DayViewTimeline date={date} items={items} loading={loading} />
    </HomeShell>
  );
}
