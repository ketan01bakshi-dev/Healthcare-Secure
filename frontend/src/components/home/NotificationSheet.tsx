"use client";

import Link from "next/link";

import OverlayBackdrop from "@/components/overlays/OverlayBackdrop";
import { useNotifications } from "@/context/NotificationContext";
import { useI18n } from "@/lib/i18n";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function NotificationSheet({ open, onClose }: Props) {
  const { t } = useI18n();
  const { items, markAllRead } = useNotifications();

  if (!open) return null;

  return (
    <>
      <OverlayBackdrop onDismiss={onClose} />
      <div className="fixed bottom-24 left-1/2 z-50 max-h-[50vh] w-[min(22rem,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-600 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
          <p className="text-sm font-semibold">{t("notifications")}</p>
          <button
            className="text-xs text-teal-700 dark:text-teal-400"
            onClick={() => markAllRead()}
            type="button"
          >
            {t("markAllRead")}
          </button>
        </div>
        <ul className="max-h-64 overflow-y-auto">
          {items.length === 0 ? (
            <li className="px-4 py-6 text-center text-sm text-slate-500">
              {t("noNotifications")}
            </li>
          ) : (
            items.map((n) => (
              <li key={n.id} className="border-b border-slate-50 dark:border-slate-800">
                {n.href ? (
                  <Link
                    className="block px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800"
                    href={n.href}
                    onClick={onClose}
                  >
                    <NotificationRow n={n} />
                  </Link>
                ) : (
                  <div className="px-4 py-3">
                    <NotificationRow n={n} />
                  </div>
                )}
              </li>
            ))
          )}
        </ul>
      </div>
    </>
  );
}

function NotificationRow({
  n,
}: {
  n: { title: string; body: string; read: boolean };
}) {
  return (
    <>
      <p
        className={`text-sm font-medium ${n.read ? "text-slate-600" : "text-slate-900 dark:text-slate-100"}`}
      >
        {n.title}
      </p>
      <p className="text-xs text-slate-500">{n.body}</p>
    </>
  );
}
