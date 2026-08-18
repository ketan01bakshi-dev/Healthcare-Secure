"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useActiveClinicRole, useClinicFeatures } from "@/components/DoctorGate";
import type { PatientCardTab } from "@/lib/clinicRoutes";
import { patientCardPath } from "@/lib/clinicRoutes";
import { useI18n } from "@/lib/i18n";

type TabDef = {
  tab: PatientCardTab;
  labelKey: string;
  roles: Array<"doctor" | "staff" | "receptionist">;
  feature?: "voice_rx";
};

const TABS: TabDef[] = [
  {
    tab: "appointment",
    labelKey: "tabAppointment",
    roles: ["doctor", "staff", "receptionist"],
  },
  {
    tab: "vitals",
    labelKey: "tabVitals",
    roles: ["doctor", "staff"],
  },
  {
    tab: "records",
    labelKey: "tabRecords",
    roles: ["doctor", "staff"],
  },
  {
    tab: "visit",
    labelKey: "tabVisit",
    roles: ["doctor"],
    feature: "voice_rx",
  },
];

export default function PatientInnerTabs({
  blindPatientId,
}: {
  blindPatientId: string;
}) {
  const { t } = useI18n();
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const searchParams = useSearchParams();
  const activeTab = (searchParams.get("tab") || "appointment") as PatientCardTab;

  const visible = TABS.filter((item) => {
    if (!item.roles.includes(role as "doctor" | "staff" | "receptionist")) {
      return false;
    }
    if (item.feature && !has(item.feature)) return false;
    return true;
  });

  return (
    <nav
      aria-label={t("patientTabs")}
      className="sticky top-0 z-10 -mx-4 flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-4 dark:border-slate-700 dark:bg-slate-950"
    >
      {visible.map((item) => {
        const active = activeTab === item.tab;
        const href = patientCardPath(blindPatientId, item.tab);
        return (
          <Link
            className={`shrink-0 border-b-2 px-3 py-3 text-sm font-medium ${
              active
                ? "border-teal-600 text-teal-800 dark:text-teal-400"
                : "border-transparent text-slate-600 dark:text-slate-400"
            }`}
            href={href}
            key={item.tab}
          >
            {t(item.labelKey)}
          </Link>
        );
      })}
    </nav>
  );
}
