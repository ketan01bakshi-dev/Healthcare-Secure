"use client";

import Link from "next/link";

import type { AppointmentRow } from "@/lib/appointmentGroups";
import { eventAccentClass, eventBgClass } from "@/lib/calendarEventStyle";
import { formatIstTime } from "@/lib/datetimeIst";
import { useI18n } from "@/lib/i18n";

type Props = {
  item: AppointmentRow;
};

export default function CalendarEventCard({ item }: Props) {
  const { t } = useI18n();
  const isVideo = (item.modality || "").toLowerCase() === "video";

  return (
    <Link
      className={`mb-2 flex overflow-hidden rounded-xl border border-slate-100 border-l-4 shadow-sm active:scale-[0.99] dark:border-slate-700 ${eventAccentClass(item.modality)} ${eventBgClass(item.modality)}`}
      href={`/home/calendar/event/?id=${encodeURIComponent(item.id)}`}
    >
      <div className="min-w-0 flex-1 px-3 py-3">
        <p className="text-xs font-medium text-slate-500">
          {item.scheduled_at ? formatIstTime(item.scheduled_at) : "—"}
        </p>
        <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
          {item.display_name}
          {item.reason ? ` · ${item.reason}` : ""}
        </p>
        {isVideo ? (
          <span className="mt-1 inline-block text-[10px] font-semibold uppercase text-sky-700 dark:text-sky-400">
            {t("videoBadge")}
          </span>
        ) : null}
      </div>
    </Link>
  );
}
