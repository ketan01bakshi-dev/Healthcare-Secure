import type { ClinicRole } from "@/lib/doctorSession";
import type { PatientCardTab } from "@/lib/clinicRoutes";

/** Role-aware ordered home tab hrefs for swipe navigation. */
export function homeTabHrefsForRole(role: ClinicRole): string[] {
  if (role === "lab") {
    return ["/home/patients/", "/labs/", "/home/profile/"];
  }
  return ["/home/calendar/", "/home/patients/", "/home/profile/"];
}

/** Resolve which home tab is active for a pathname. */
export function activeHomeTabHref(
  pathname: string,
  hrefs: string[],
): string {
  const match = hrefs.find((href) => {
    if (href === "/home/patients/") {
      return (
        pathname.startsWith("/home/patients") &&
        !pathname.startsWith("/home/patients/new")
      );
    }
    if (href === "/home/calendar/") {
      return pathname.startsWith("/home/calendar");
    }
    return pathname.startsWith(href.replace(/\/$/, ""));
  });
  return match || hrefs[0];
}

type PatientTabDef = {
  tab: PatientCardTab;
  roles: Array<"doctor" | "staff" | "receptionist">;
  feature?: "voice_rx";
};

const PATIENT_TABS: PatientTabDef[] = [
  {
    tab: "appointment",
    roles: ["doctor", "staff", "receptionist"],
  },
  {
    tab: "vitals",
    roles: ["doctor", "staff"],
  },
  {
    tab: "records",
    roles: ["doctor", "staff"],
  },
  {
    tab: "visit",
    roles: ["doctor"],
    feature: "voice_rx",
  },
];

/** Role/feature-aware patient card tabs for swipe navigation. */
export function patientTabsForRole(
  role: ClinicRole,
  hasFeature: (f: "voice_rx") => boolean,
): PatientCardTab[] {
  return PATIENT_TABS.filter((item) => {
    if (role === "lab") return false;
    if (!item.roles.includes(role as "doctor" | "staff" | "receptionist")) {
      return false;
    }
    if (item.feature && !hasFeature(item.feature)) return false;
    return true;
  }).map((item) => item.tab);
}
