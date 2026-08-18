"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import type { ClinicRole } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

type NavItem = {
  href: string;
  labelKey: string;
  match: (path: string) => boolean;
  feature?: "voice_rx" | "labs";
};

function navItemsForRole(role: ClinicRole): NavItem[] {
  if (role === "lab") {
    return [
      {
        href: "/today/",
        labelKey: "navToday",
        match: (p) => p.startsWith("/today"),
      },
      {
        href: "/labs/",
        labelKey: "navLabs",
        match: (p) => p.startsWith("/labs"),
        feature: "labs",
      },
      {
        href: "/more/",
        labelKey: "navMore",
        match: (p) => p.startsWith("/more"),
      },
    ];
  }

  if (role === "receptionist") {
    return [
      {
        href: "/today/",
        labelKey: "navToday",
        match: (p) => p.startsWith("/today"),
      },
      {
        href: "/more/",
        labelKey: "navMore",
        match: (p) => p.startsWith("/more"),
      },
    ];
  }

  // Staff: Patient Info, Vitals, Records, More (no Visit)
  // Doctor: all of the above + Visit
  const items: NavItem[] = [
    {
      href: "/today/",
      labelKey: "navToday",
      match: (p) => p.startsWith("/today"),
    },
    {
      href: "/patient/",
      labelKey: "navPatient",
      match: (p) => p.startsWith("/patient"),
    },
    {
      href: "/records/",
      labelKey: "navRecords",
      match: (p) => p.startsWith("/records"),
    },
  ];
  if (role === "doctor") {
    items.push({
      href: "/visit/",
      labelKey: "navVisit",
      match: (p) => p.startsWith("/visit"),
      feature: "voice_rx",
    });
  }
  items.push({
    href: "/more/",
    labelKey: "navMore",
    match: (p) => p.startsWith("/more"),
  });
  return items;
}

export default function ClinicNav() {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const pathname = usePathname() || "/";

  const visible = navItemsForRole(role).filter(
    (item) => !item.feature || has(item.feature),
  );

  return (
    <nav
      aria-label={t("clinicNav")}
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
    >
      <ul className="mx-auto flex max-w-3xl items-stretch justify-around gap-0 px-1 pt-1">
        {visible.map((item) => {
          const active = item.match(pathname);
          return (
            <li key={item.href} className="min-w-0 flex-1">
              <Link
                href={item.href}
                className={`flex min-h-14 flex-col items-center justify-center rounded-lg px-1 py-2 text-center text-[11px] font-medium leading-tight sm:text-xs ${
                  active
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t(item.labelKey)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
