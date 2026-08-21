import type { ClinicRole } from "@/lib/doctorSession";

export type PatientCardTab = "appointment" | "vitals" | "records" | "visit";

/** Patient card URL (static-export friendly query params). */
export function patientCardPath(
  blindPatientId: string,
  tab: PatientCardTab = "appointment",
): string {
  const params = new URLSearchParams({ id: blindPatientId, tab });
  return `/home/patient/?${params.toString()}`;
}

/** Where to send the user after locking a patient from directory or waiting list. */
export function pathAfterPatientLock(
  role: ClinicRole,
  blindPatientId: string,
): string {
  if (role === "lab") return "/labs/";
  if (role === "doctor") return patientCardPath(blindPatientId, "visit");
  if (role === "staff") return patientCardPath(blindPatientId, "vitals");
  return patientCardPath(blindPatientId, "appointment");
}

/** Default home landing after PIN. */
export const HOME_LANDING = "/home/calendar/";
