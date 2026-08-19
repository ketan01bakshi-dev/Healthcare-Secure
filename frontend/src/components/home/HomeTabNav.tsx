"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useActiveClinicRole } from "@/components/DoctorGate";
import { useI18n } from "@/lib/i18n";

type TabItem = {
  href: string;
  labelKey: string;
  icon: string;
  match: (path: string) => boolean;
  labOnly?: boolean;
  hideForLab?: boolean;
};

const TABS: TabItem[] = [
  {
    href: "/home/calendar/",
    labelKey: "navCalendar",
    icon: "📅",
    match: (p) => p.startsWith("/home/calendar"),
    hideForLab: true,
  },
  {
    href: "/home/patients/",
    labelKey: "navPatients",
    icon: "👤",
    match: (p) =>
      p.startsWith("/home/patients") && !p.startsWith("/home/patients/new"),
  },
  {
    href: "/labs/",
    labelKey: "navLabs",
    icon: "🧪",
    match: (p) => p.startsWith("/labs"),
    labOnly: true,
  },
  {
    href: "/home/profile/",
    labelKey: "navProfile",
    icon: "⚙",
    match: (p) => p.startsWith("/home/profile"),
  },
];

export default function HomeTabNav() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const pathname = usePathname() || "/";

  const visible = TABS.filter((tab) => {
    if (tab.labOnly) return role === "lab";
    if (tab.hideForLab) return role !== "lab";
    return true;
  });

  return (
    <nav
      aria-label={t("clinicNav")}
      className="fixed bottom-0 left-0 right-0 z-30 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur dark:border-slate-700 dark:bg-slate-900/95"
    >
      <ul className="mx-auto flex max-w-3xl items-stretch justify-around gap-0 px-1 pt-1">
        {visible.map((tab) => {
          const active = tab.match(pathname);
          return (
            <li key={tab.href} className="min-w-0 flex-1">
              <Link
                href={tab.href}
                className={`flex min-h-14 flex-col items-center justify-center rounded-lg px-1 py-2 text-center text-[11px] font-medium leading-tight sm:text-xs ${
                  active
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                    : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                }`}
              >
                <span aria-hidden className="mb-0.5 text-base leading-none">
                  {tab.icon}
                </span>
                {t(tab.labelKey)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
