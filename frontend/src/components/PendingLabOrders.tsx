"use client";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { ALPHA_RECOMMENDED_DIAGNOSTICS } from "@/lib/recommendedDiagnostics";
import { useI18n } from "@/lib/i18n";

type Props = {
  onSelectTest?: (testName: string) => void;
};

export default function PendingLabOrders({ onSelectTest }: Props) {
  const { t } = useI18n();
  const { locked, selectedDiagnostics } = usePatient();

  const pending = ALPHA_RECOMMENDED_DIAGNOSTICS.filter((item) =>
    selectedDiagnostics.includes(item.id),
  );

  if (!locked || pending.length === 0) {
    return null;
  }

  return (
    <CollapsibleSection
      defaultOpen
      hint={t("pendingLabOrdersHint")}
      title={t("pendingLabOrders")}
    >
      <ul className="space-y-2">
        {pending.map((item) => (
          <li key={item.id}>
            <button
              className="flex w-full min-h-11 items-center justify-between rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-left text-sm text-sky-950 hover:bg-sky-100"
              onClick={() => onSelectTest?.(item.label)}
              type="button"
            >
              <span>{item.label}</span>
              <span className="text-xs text-sky-700">{t("enterResult")}</span>
            </button>
          </li>
        ))}
      </ul>
    </CollapsibleSection>
  );
}
