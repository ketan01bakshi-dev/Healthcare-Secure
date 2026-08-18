"use client";

import { useEffect, useState } from "react";

import ClinicAnalytics from "@/components/ClinicAnalytics";
import HomeShell from "@/components/home/HomeShell";
import { useClinicFeatures } from "@/components/DoctorGate";
import { useTheme } from "@/context/ThemeContext";
import { APP_BUILD_ID } from "@/lib/appBuild";
import { getApiBaseUrl, isNativeApp } from "@/lib/apiBase";
import { getClinicGate, getClinicUser } from "@/lib/doctorSession";
import {
  hapticsEnabled,
  setHapticsEnabled,
} from "@/lib/haptics";
import { LanguageToggle, useI18n } from "@/lib/i18n";

export default function ProfilePage() {
  const { t } = useI18n();
  const { has } = useClinicFeatures();
  const { theme, toggleTheme } = useTheme();
  const [apiUrl, setApiUrl] = useState("");
  const [native, setNative] = useState(false);
  const [haptics, setHaptics] = useState(true);
  const user = getClinicUser();
  const gate = getClinicGate();

  useEffect(() => {
    setApiUrl(getApiBaseUrl());
    setNative(isNativeApp());
    setHaptics(hapticsEnabled());
  }, []);

  return (
    <HomeShell showFab={false} showNotification title={t("navProfile")}>
      <div className="space-y-6">
        <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            {user?.display_name || "—"}
          </p>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            {gate?.name ? `${gate.name} · ` : ""}
            {user?.role || ""}
          </p>
        </section>

        <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <div className="flex items-center justify-between gap-3 py-2">
            <span className="text-sm text-slate-700 dark:text-slate-300">
              {t("language")}
            </span>
            <LanguageToggle />
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 py-3 dark:border-slate-800">
            <span className="text-sm text-slate-700 dark:text-slate-300">
              {t("darkMode")}
            </span>
            <button
              className="min-h-10 rounded-lg border border-slate-200 px-4 text-sm dark:border-slate-600"
              onClick={toggleTheme}
              type="button"
            >
              {theme === "dark" ? t("darkModeOn") : t("darkModeOff")}
            </button>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 py-3 dark:border-slate-800">
            <span className="text-sm text-slate-700 dark:text-slate-300">
              {t("haptics")}
            </span>
            <button
              className="min-h-10 rounded-lg border border-slate-200 px-4 text-sm dark:border-slate-600"
              onClick={() => {
                const next = !haptics;
                setHaptics(next);
                setHapticsEnabled(next);
              }}
              type="button"
            >
              {haptics ? t("on") : t("off")}
            </button>
          </div>
        </section>

        {apiUrl ? (
          <p className="break-all font-mono text-xs text-slate-500">
            {t("clinicServer")}: {apiUrl}
          </p>
        ) : null}
        <p className="font-mono text-xs text-slate-500">
          UI build: {APP_BUILD_ID}
          {native ? " · native app" : " · browser"}
        </p>
        <p className="text-xs text-slate-500">{t("moreSignOutHint")}</p>
        {has("analytics") ? <ClinicAnalytics /> : null}
      </div>
    </HomeShell>
  );
}
