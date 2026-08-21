"use client";

import { useNotifications } from "@/context/NotificationContext";
import { useI18n } from "@/lib/i18n";
import { lightHaptic } from "@/lib/haptics";

type Props = {
  onClick: () => void;
  className?: string;
};

export default function NotificationFab({ onClick, className = "" }: Props) {
  const { t } = useI18n();
  const { unreadCount } = useNotifications();

  return (
    <button
      className={`fixed left-1/2 z-20 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-800 shadow-md active:scale-95 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 ${className}`}
      onClick={() => {
        lightHaptic();
        onClick();
      }}
      type="button"
    >
      {t("notifications")}
      {unreadCount > 0 ? (
        <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
          {unreadCount > 9 ? "9+" : unreadCount}
        </span>
      ) : null}
    </button>
  );
}
