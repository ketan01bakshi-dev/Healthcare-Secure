"use client";

import type { AppointmentDayGroup } from "@/lib/appointmentGroups";
import CalendarEventCard from "@/components/calendar/CalendarEventCard";
import { useI18n } from "@/lib/i18n";

type Props = {
  groups: AppointmentDayGroup[];
  loading?: boolean;
};

export default function ScheduleViewList({ groups, loading }: Props) {
  const { t } = useI18n();

  if (loading) {
    return <p className="text-sm text-slate-500">{t("loadingAppointments")}</p>;
  }

  if (groups.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-700">
        {t("noAppointments")}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.dayKey}>
          <h2 className="sticky top-[4.5rem] z-[1] bg-white/95 py-2 text-sm font-semibold text-slate-700 backdrop-blur dark:bg-slate-950/95 dark:text-slate-300">
            {group.label}
          </h2>
          {group.items.map((item) => (
            <CalendarEventCard item={item} key={item.id} />
          ))}
        </section>
      ))}
    </div>
  );
}
