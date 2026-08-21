"use client";

import { useCallback, useEffect, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { formatIst } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

type Actor = { display_name?: string; role?: string };

type EncounterData = {
  type?: string;
  action?: string;
  summary?: string;
  document_kind?: string;
  title?: string;
  diagnoses?: unknown;
  entered_by?: Actor;
  signed_by?: Actor;
  entered_at_display?: string;
  issued_at_display?: string;
};

type HistoryRecord = {
  id: string;
  created_at: string | null;
  encounter_data: EncounterData | null;
};

function actionLabel(data: EncounterData | null): string {
  if (!data) return "Update";
  if (data.type === "audit" && data.action === "phone_change") {
    return data.summary || "Mobile number updated";
  }
  if (data.type === "vitals") return "Vitals / notes saved";
  if (data.type === "health_profile") return "Ongoing medication & health issues updated";
  if (data.type === "obstetric_profile") return "Obstetric profile updated";
  if (data.type === "document") {
    const kind = (data.document_kind || "document").replace(/_/g, " ");
    return data.title ? `Uploaded: ${data.title}` : `Uploaded ${kind}`;
  }
  if (data.type === "prescription" || !data.type) {
    const dx = Array.isArray(data.diagnoses)
      ? data.diagnoses.filter((x): x is string => typeof x === "string")
      : [];
    return dx.length
      ? `Prescription signed · ${dx.slice(0, 2).join(", ")}`
      : "Prescription signed";
  }
  return data.type;
}

function whoLabel(data: EncounterData | null): string {
  const actor = data?.entered_by || data?.signed_by;
  if (!actor?.display_name) return "Clinic team";
  const role =
    actor.role === "doctor"
      ? "Doctor"
      : actor.role === "staff"
        ? "Staff"
        : actor.role === "receptionist"
          ? "Reception"
          : actor.role === "lab"
          ? "Lab"
          : null;
  return role ? `${actor.display_name} (${role})` : actor.display_name;
}

export default function PatientAuditTrail() {
  const { t } = useI18n();
  const { locked, rawIdentifier, historyVersion } = usePatient();
  const [items, setItems] = useState<
    { id: string; when: string; what: string; who: string }[]
  >([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "empty">(
    "idle",
  );

  const load = useCallback(async (raw: string) => {
    setStatus("loading");
    try {
      const response = await apiFetch("/api/v1/history/search", {
        method: "POST",
        body: JSON.stringify({ raw_identifier: raw }),
      });
      if (!response.ok) {
        setItems([]);
        setStatus("empty");
        return;
      }
      const data = (await response.json()) as HistoryRecord[];
      const mapped = (data || []).map((r) => {
        const d = r.encounter_data;
        const when =
          d?.entered_at_display ||
          d?.issued_at_display ||
          (r.created_at ? formatIst(r.created_at) : "—");
        return {
          id: r.id,
          when,
          what: actionLabel(d),
          who: whoLabel(d),
        };
      });
      setItems(mapped);
      setStatus(mapped.length ? "ready" : "empty");
    } catch {
      setItems([]);
      setStatus("empty");
    }
  }, []);

  useEffect(() => {
    if (!locked || !rawIdentifier.trim()) {
      setItems([]);
      setStatus("idle");
      return;
    }
    void load(rawIdentifier.trim());
  }, [locked, rawIdentifier, historyVersion, load]);

  if (!locked) return null;

  return (
    <CollapsibleSection
      aria-label={t("activityLog")}
      hint={t("activityLogHint")}
      title={t("activityLog")}
    >
      {status === "loading" ? (
        <p className="text-sm text-slate-500">{t("loadingEllipsis")}</p>
      ) : null}
      {status === "empty" ? (
        <p className="text-sm text-slate-500">{t("noActivityYet")}</p>
      ) : null}
      {status === "ready" ? (
        <ul className="divide-y divide-slate-100">
          {items.map((item) => (
            <li className="py-3" key={item.id}>
              <p className="text-sm font-medium text-slate-900">{item.what}</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {item.who} · {item.when}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </CollapsibleSection>
  );
}
