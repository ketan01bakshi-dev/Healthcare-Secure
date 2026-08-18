/**
 * Baked into the static Capacitor export at `next build` time.
 * Bump this whenever shipping a share APK so phones can show which UI build they run.
 */
export const APP_BUILD_ID = "2026-08-14-doctor-today-first";

/** Features present in this source tree (for stale-APK diagnosis). */
export const APP_BUNDLE_MARKERS = {
  patientBilling: true,
  payQr: true,
  patientInfoNav: true,
} as const;
