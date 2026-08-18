"use client";

import { useEffect, useState } from "react";

import ClinicAnalytics from "@/components/ClinicAnalytics";
import CollapsibleSection from "@/components/CollapsibleSection";
import { useClinicFeatures } from "@/components/DoctorGate";
import { APP_BUILD_ID } from "@/lib/appBuild";
import { getApiBaseUrl, isNativeApp } from "@/lib/apiBase";
import { LanguageToggle, useI18n } from "@/lib/i18n";

export default function MorePage() {
  const { t } = useI18n();
  const { has } = useClinicFeatures();
  const [apiUrl, setApiUrl] = useState("");
  const [native, setNative] = useState(false);

  useEffect(() => {
    setApiUrl(getApiBaseUrl());
    setNative(isNativeApp());
  }, []);

  return (
    <div className="space-y-6">
      <CollapsibleSection title={t("navMore")}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-600">{t("language")}</p>
          <LanguageToggle />
        </div>
        {apiUrl ? (
          <p className="mt-1 break-all font-mono text-xs text-slate-500">
            {t("clinicServer")}: {apiUrl}
          </p>
        ) : null}
        <p className="mt-1 font-mono text-xs text-slate-500">
          UI build: {APP_BUILD_ID}
          {native ? " · native app" : " · browser"}
        </p>
        <p className="text-xs text-slate-500">{t("moreSignOutHint")}</p>
      </CollapsibleSection>
      {has("analytics") ? <ClinicAnalytics /> : null}
    </div>
  );
}
