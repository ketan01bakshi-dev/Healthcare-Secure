"use client";

const STRINGS = {
  clinicServer: "Clinic server",
  clinicServerHint: "Use the clinic backend URL when this device is not on localhost.",
  clinicServerLoopback:
    "This device cannot reach a localhost clinic server. Enter the clinic backend URL.",
  saveReconnect: "Save and reconnect",
  signOut: "Sign out",
} as const;

type TranslationKey = keyof typeof STRINGS;

export function useI18n() {
  return {
    t: (key: TranslationKey) => STRINGS[key] || key,
  };
}
