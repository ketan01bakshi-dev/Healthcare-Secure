"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  alphabetIndexLetters,
  groupPatientsByLetter,
  type PatientRow,
} from "@/lib/groupPatientsByLetter";
import { patientCardPath } from "@/lib/clinicRoutes";
import { patientInitials } from "@/lib/patientInitials";
import { formatIst } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";
import { usePatient } from "@/context/PatientContext";

type Props = {
  onSelect?: (id: string) => void;
};

export default function PatientsList({ onSelect }: Props) {
  const { t } = useI18n();
  const router = useRouter();
  const { lockFromDirectory } = usePatient();
  const [items, setItems] = useState<PatientRow[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      const qs = params.toString();
      const res = await apiFetch(
        `/api/v1/history/patients${qs ? `?${qs}` : ""}`,
      );
      if (!res.ok) return;
      const data = (await res.json()) as PatientRow[];
      setItems(Array.isArray(data) ? data : []);
    } catch {
      /* offline */
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 200);
    return () => window.clearTimeout(id);
  }, [load]);

  const groups = groupPatientsByLetter(items);
  const letters = alphabetIndexLetters(groups);

  async function openPatient(blindId: string) {
    if (onSelect) {
      onSelect(blindId);
      return;
    }
    setBusy(true);
    try {
      const lockedId = await lockFromDirectory(blindId);
      router.push(patientCardPath(lockedId, "appointment"));
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }

  function scrollToLetter(letter: string) {
    sectionRefs.current[letter]?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <div className="relative">
      <div className="mb-4 px-1">
        <input
          className="min-h-12 w-full rounded-full border-0 bg-slate-100 px-5 text-sm outline-none ring-teal-500 focus:ring-2 dark:bg-slate-800 dark:text-slate-100"
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("searchPatientsPlaceholder")}
          value={query}
        />
      </div>

      {loading ? (
        <p className="text-sm text-slate-500">{t("loadingPatients")}</p>
      ) : groups.length === 0 ? (
        <p className="text-center text-sm text-slate-500">{t("noPatientsYet")}</p>
      ) : (
        <div className="pr-6">
          {groups.map((group) => (
            <section
              key={group.letter}
              ref={(el) => {
                sectionRefs.current[group.letter] = el;
              }}
            >
              <h2 className="sticky top-[4.5rem] z-[1] bg-slate-100/95 px-3 py-1.5 text-xs font-bold text-teal-800 backdrop-blur dark:bg-slate-800/95 dark:text-teal-300">
                {group.letter}
              </h2>
              <ul>
                {group.items.map((item) => (
                  <li key={item.blind_patient_id}>
                    <button
                      className="flex w-full min-h-14 items-center gap-3 border-b border-slate-50 px-3 py-2 text-left active:bg-slate-50 dark:border-slate-800 dark:active:bg-slate-800"
                      disabled={busy || (!item.has_phone && !item.clinic_mrn)}
                      onClick={() => void openPatient(item.blind_patient_id)}
                      type="button"
                    >
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-100 text-sm font-semibold text-teal-900 dark:bg-teal-900/60 dark:text-teal-100">
                        {patientInitials(item.display_name)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                          {item.display_name}
                        </span>
                        <span className="block truncate text-xs text-slate-500">
                          {item.phone_last4 ? `***${item.phone_last4}` : "—"}
                          {item.clinic_mrn ? ` · ${item.clinic_mrn}` : ""}
                          {` · ${item.visit_count} visit${item.visit_count === 1 ? "" : "s"}`}
                          {item.last_seen_at
                            ? ` · ${formatIst(item.last_seen_at)}`
                            : ""}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {!loading && letters.length > 1 ? (
        <div className="fixed right-1 top-1/2 z-20 flex -translate-y-1/2 flex-col text-[10px] font-semibold text-teal-700 dark:text-teal-400">
          {letters.map((letter) => (
            <button
              className="px-1 py-0.5"
              key={letter}
              onClick={() => scrollToLetter(letter)}
              type="button"
            >
              {letter}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
