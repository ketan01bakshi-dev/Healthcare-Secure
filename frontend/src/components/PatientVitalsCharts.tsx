"use client";

import { useCallback, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import VitalsTrendCharts, {
  type VitalsTrendPoint,
} from "@/components/VitalsTrendCharts";
import { usePatient } from "@/context/PatientContext";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

/** Weight & BP charts for the locked patient; refreshes when vitals are saved. */
export default function PatientVitalsCharts() {
  const { t } = useI18n();
  const { locked, rawIdentifier, historyVersion } = usePatient();
  const [points, setPoints] = useState<VitalsTrendPoint[]>([]);
  const [alerts, setAlerts] = useState<
    { code: string; severity: string; message: string }[]
  >([]);

  const load = useCallback(async () => {
    if (!locked || !rawIdentifier) {
      setPoints([]);
      setAlerts([]);
      return;
    }
    try {
      const res = await apiFetch("/api/v1/analytics/vitals-trend", {
        method: "POST",
        body: JSON.stringify({ raw_identifier: rawIdentifier }),
      });
      if (!res.ok) {
        setPoints([]);
        setAlerts([]);
        return;
      }
      const data = (await res.json()) as {
        points?: VitalsTrendPoint[];
        alerts?: { code: string; severity: string; message: string }[];
      };
      setPoints(Array.isArray(data.points) ? data.points : []);
      setAlerts(Array.isArray(data.alerts) ? data.alerts : []);
    } catch {
      setPoints([]);
      setAlerts([]);
    }
  }, [locked, rawIdentifier]);

  useEffect(() => {
    void load();
  }, [load, historyVersion]);

  if (!locked) return null;

  return (
    <CollapsibleSection title={t("vitalsTrend")}>
      <VitalsTrendCharts
        points={points}
        emptyHint={t("noVitalsYet")}
        alerts={alerts}
      />
    </CollapsibleSection>
  );
}
