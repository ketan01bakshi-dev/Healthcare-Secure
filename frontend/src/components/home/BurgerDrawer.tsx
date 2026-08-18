"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import OverlayBackdrop from "@/components/overlays/OverlayBackdrop";
import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import { useI18n } from "@/lib/i18n";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function BurgerDrawer({ open, onClose }: Props) {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const pathname = usePathname() || "";

  if (!open) return null;

  const onCalendar = pathname.startsWith("/home/calendar");

  return (
    <>
      <OverlayBackdrop onDismiss={onClose} />
      <aside className="fixed left-0 top-0 z-50 flex h-full w-[min(18rem,85vw)] flex-col border-r border-slate-200 bg-white pt-[max(1rem,env(safe-area-inset-top))] shadow-xl dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 pb-3 dark:border-slate-800">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Menu
          </p>
          <button
            aria-label={t("cancel")}
            className="min-h-10 min-w-10 rounded-lg text-slate-500"
            onClick={onClose}
            type="button"
          >
            ✕
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {onCalendar ? (
            <div className="mb-4">
              <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t("calendarView")}
              </p>
              <DrawerLink
                active={pathname === "/home/calendar/" || pathname === "/home/calendar"}
                href="/home/calendar/"
                label={t("viewSchedule")}
                onNavigate={onClose}
              />
              <DrawerLink
                active={pathname.startsWith("/home/calendar/day")}
                href="/home/calendar/day/"
                label={t("viewDay")}
                onNavigate={onClose}
              />
              <DrawerLink
                active={pathname.startsWith("/home/calendar/month")}
                href="/home/calendar/month/"
                label={t("viewMonth")}
                onNavigate={onClose}
              />
            </div>
          ) : null}

          <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {t("clinicTools")}
          </p>
          {role === "lab" || has("labs") ? (
            <DrawerLink
              active={pathname.startsWith("/labs")}
              href="/labs/"
              label={t("navLabs")}
              onNavigate={onClose}
            />
          ) : null}
          <DrawerLink
            active={pathname.startsWith("/home/profile")}
            href="/home/profile/"
            label={t("navProfile")}
            onNavigate={onClose}
          />
        </nav>
      </aside>
    </>
  );
}

function DrawerLink({
  href,
  label,
  active,
  onNavigate,
}: {
  href: string;
  label: string;
  active: boolean;
  onNavigate: () => void;
}) {
  return (
    <Link
      className={`mb-1 flex min-h-12 items-center rounded-lg px-3 text-sm font-medium ${
        active
          ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
          : "text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800"
      }`}
      href={href}
      onClick={onNavigate}
    >
      {label}
    </Link>
  );
}
