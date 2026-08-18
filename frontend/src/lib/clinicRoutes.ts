import type { ClinicRole } from "@/lib/doctorSession";

/** Where to send the user after locking a patient from directory or waiting list. */
export function pathAfterPatientLock(role: ClinicRole): string {
  if (role === "lab") return "/labs/";
  if (role === "doctor") return "/visit/";
  if (role === "staff") return "/patient/";
  return "/today/";
}
