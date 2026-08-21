const HAPTICS_KEY = "healthcare_haptics";

export function hapticsEnabled(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(HAPTICS_KEY) !== "off";
}

export function setHapticsEnabled(on: boolean): void {
  localStorage.setItem(HAPTICS_KEY, on ? "on" : "off");
}

export function lightHaptic(): void {
  if (!hapticsEnabled()) return;
  try {
    if (typeof navigator !== "undefined" && navigator.vibrate) {
      navigator.vibrate(10);
    }
  } catch {
    /* ignore */
  }
}
