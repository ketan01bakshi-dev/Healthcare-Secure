"use client";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import {
  ALPHA_RECOMMENDED_DIAGNOSTICS,
  formatInvestigationsLine,
} from "@/lib/recommendedDiagnostics";
import { useI18n } from "@/lib/i18n";

export default function RecommendedDiagnostics() {
  const { t } = useI18n();
  const {
    locked,
    selectedDiagnostics,
    dismissedDiagnostics,
    toggleRecommendedDiagnostic,
    dismissRecommendedDiagnostic,
  } = usePatient();

  const visible = ALPHA_RECOMMENDED_DIAGNOSTICS.filter(
    (item) => !dismissedDiagnostics.includes(item.id),
  );

  if (visible.length === 0) {
    return null;
  }

  const selectedLabels = ALPHA_RECOMMENDED_DIAGNOSTICS.filter((item) =>
    selectedDiagnostics.includes(item.id),
  ).map((item) => item.label);
  const investigationsLine = formatInvestigationsLine(selectedLabels);

  return (
    <CollapsibleSection
      hint={t("recommendedDiagnosticsHint")}
      title={
        <span>
          {t("recommendedDiagnostics")}{" "}
          <span className="font-normal normal-case text-slate-400">
            · प्रमुख जांचें
          </span>
        </span>
      }
    >
      <p className="mb-3 text-sm text-slate-600">
        {t("recommendedDiagnosticsHelp")}
      </p>
      <ul className="space-y-1">
        {visible.map((item) => {
          const selected = selectedDiagnostics.includes(item.id);
          return (
            <li
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${
                selected
                  ? "border-emerald-200 bg-emerald-50/80"
                  : "border-slate-200 bg-white"
              }`}
              key={item.id}
            >
              <label className="flex min-h-10 flex-1 cursor-pointer items-center gap-3">
                <input
                  checked={selected}
                  className="h-4 w-4 shrink-0 rounded border-slate-300"
                  disabled={!locked}
                  onChange={() => toggleRecommendedDiagnostic(item.id)}
                  type="checkbox"
                />
                <span
                  className={`text-sm ${
                    selected ? "font-medium text-emerald-950" : "text-slate-800"
                  }`}
                >
                  {item.label}
                </span>
              </label>
              <button
                className="shrink-0 rounded px-2 py-1 text-xs text-slate-500 underline-offset-2 hover:text-slate-800 hover:underline disabled:opacity-40"
                disabled={!locked}
                onClick={() => dismissRecommendedDiagnostic(item.id)}
                title={t("recommendedDiagnosticsDismiss")}
                type="button"
              >
                {t("recommendedDiagnosticsDismiss")}
              </button>
            </li>
          );
        })}
      </ul>
      {investigationsLine ? (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {investigationsLine}
        </p>
      ) : null}
    </CollapsibleSection>
  );
}
