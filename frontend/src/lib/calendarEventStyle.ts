/** Left accent bar color by appointment modality (Google Calendar–like). */
export function eventAccentClass(modality?: string): string {
  if ((modality || "").toLowerCase() === "video") {
    return "border-l-sky-500";
  }
  return "border-l-teal-600";
}

export function eventBgClass(modality?: string): string {
  if ((modality || "").toLowerCase() === "video") {
    return "bg-sky-50 dark:bg-sky-950/40";
  }
  return "bg-teal-50 dark:bg-teal-950/40";
}
