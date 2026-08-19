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
  roles?: Array<"doctor" | "staff" | "receptionist" | "lab">;
};

const TABS: TabItem[] = [
  {
    href: "/home/calendar/",
    labelKey: "navCalendar",
    icon: "📅",
    match: (p) => p.startsWith("/home/calendar"),
  },
  {
    href: "/home/patients/",
    labelKey: "navPatients",
    icon: "👤",
    match: (p) =>
      p.startsWith("/home/patients") && !p.startsWith("/home/patients/new"),
  },
  {
    href: "/home/search/",
    labelKey: "navSearch",
    icon: "🔍",
    match: (p) => p.startsWith("/home/search"),
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
    if (!tab.roles) return role !== "lab" || tab.href.includes("patients");
    return tab.roles.includes(role);
  });

  if (role === "lab") {
    return (
      <nav
        aria-label={t("clinicNav")}
        className="fixed bottom-0 left-0 right-0 z-30 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur dark:border-slate-700 dark:bg-slate-900/95"
      >
        <ul className="mx-auto flex max-w-3xl items-stretch justify-around px-1 pt-1">
          <li className="min-w-0 flex-1">
            <Link
              href="/home/patients/"
              className={`flex min-h-14 flex-col items-center justify-center rounded-lg px-1 py-2 text-center text-[11px] font-medium ${
                pathname.startsWith("/home/patient")
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "text-slate-600 dark:text-slate-300"
              }`}
            >
              <span className="text-base leading-none">👤</span>
              {t("navPatients")}
            </Link>
          </li>
          <li className="min-w-0 flex-1">
            <Link
              href="/labs/"
              className={`flex min-h-14 flex-col items-center justify-center rounded-lg px-1 py-2 text-center text-[11px] font-medium ${
                pathname.startsWith("/labs")
                  ? "bg-slate-900 text-white"
                  : "text-slate-600"
              }`}
            >
              <span className="text-base leading-none">🧪</span>
              {t("navLabs")}
            </Link>
          </li>
        </ul>
      </nav>
    );
  }

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
