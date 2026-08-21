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

/* ── Types ────────────────────────────────────────────────────────────────── */

type ClinicalSearchMatch = {
  blind_patient_id: string;
  display_name: string;
  phone_last4: string;
  clinic_mrn: string;
  match_type:
    | "name"
    | "medication"
    | "diagnosis"
    | "symptom"
    | "treatment"
    | "observation"
    | "lab_result"
    | "document";
  match_text: string;
  record_date: string | null;
};

type Props = {
  onSelect?: (id: string) => void;
};

/* ── Match badge ──────────────────────────────────────────────────────────── */

const BADGE_CLS: Record<ClinicalSearchMatch["match_type"], string> = {
  name: "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
  medication: "bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-200",
  diagnosis: "bg-violet-100 text-violet-800 dark:bg-violet-900/60 dark:text-violet-200",
  symptom: "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200",
  treatment: "bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-200",
  observation: "bg-orange-100 text-orange-800 dark:bg-orange-900/60 dark:text-orange-200",
  lab_result: "bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-200",
  document: "bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-200",
};

const BADGE_LABEL_KEY: Record<ClinicalSearchMatch["match_type"], string> = {
  name: "searchMatchPatient",
  medication: "searchMatchMedication",
  diagnosis: "searchMatchDiagnosis",
  symptom: "searchMatchSymptom",
  treatment: "searchMatchTreatment",
  observation: "searchMatchObservation",
  lab_result: "searchMatchLab",
  document: "searchMatchDocument",
};

function MatchBadge({ type }: { type: ClinicalSearchMatch["match_type"] }) {
  const { t } = useI18n();
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${BADGE_CLS[type] ?? BADGE_CLS.name}`}
    >
      {t(BADGE_LABEL_KEY[type] ?? "searchMatchPatient")}
    </span>
  );
}

/* ── Highlight matched term in text ──────────────────────────────────────── */

function Highlight({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-200 dark:bg-yellow-700 rounded px-0.5">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  );
}

/* ── Main component ───────────────────────────────────────────────────────── */

export default function PatientsList({ onSelect }: Props) {
  const { t } = useI18n();
  const router = useRouter();
  const { lockFromDirectory } = usePatient();
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Directory mode (no query): A–Z grouped patient list
  const [dirItems, setDirItems] = useState<PatientRow[]>([]);
  const [dirLoading, setDirLoading] = useState(true);

  // Search mode (query ≥ 2 chars): universal clinical search
  const [searchResults, setSearchResults] = useState<ClinicalSearchMatch[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  const isSearchMode = query.trim().length >= 2;

  /* Load directory */
  const loadDirectory = useCallback(async () => {
    setDirLoading(true);
    try {
      const res = await apiFetch("/api/v1/history/patients");
      if (!res.ok) return;
      const data = (await res.json()) as PatientRow[];
      setDirItems(Array.isArray(data) ? data : []);
    } catch {
      /* offline */
    } finally {
      setDirLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDirectory();
  }, [loadDirectory]);

  /* Universal clinical search (debounced) */
  useEffect(() => {
    if (!isSearchMode) {
      setSearchResults([]);
      return;
    }
    const id = window.setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await apiFetch(
          `/api/v1/history/clinical-search?q=${encodeURIComponent(query.trim())}`,
        );
        if (!res.ok) return;
        const data = (await res.json()) as ClinicalSearchMatch[];
        setSearchResults(Array.isArray(data) ? data : []);
      } catch {
        /* offline */
      } finally {
        setSearchLoading(false);
      }
    }, 300);
    return () => window.clearTimeout(id);
  }, [query, isSearchMode]);

  const groups = groupPatientsByLetter(dirItems);
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

  /* ── Render ── */
  return (
    <div className="relative">

      {/* Search bar */}
      <div className="mb-4 flex items-center gap-2 px-1">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
            🔍
          </span>
          <input
            ref={inputRef}
            className="min-h-12 w-full rounded-full border-0 bg-slate-100 pl-10 pr-4 text-sm outline-none ring-teal-500 focus:ring-2 dark:bg-slate-800 dark:text-slate-100"
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("universalSearchPlaceholder")}
            value={query}
          />
          {query ? (
            <button
              className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400"
              onClick={() => { setQuery(""); inputRef.current?.focus(); }}
              type="button"
              aria-label={t("clearSearch")}
            >
              ✕
            </button>
          ) : null}
        </div>
      </div>

      {/* ── SEARCH MODE ── */}
      {isSearchMode ? (
        <div>
          {searchLoading ? (
            <p className="text-sm text-slate-500">{t("searching")}</p>
          ) : searchResults.length === 0 ? (
            <p className="text-center text-sm text-slate-500">{t("noSearchResults")}</p>
          ) : (
            <>
              <p className="mb-2 px-1 text-xs text-slate-500">
                {searchResults.length} {t("searchResultsFor")} &ldquo;{query.trim()}&rdquo;
              </p>
              <ul>
                {searchResults.map((match, i) => (
                  <li key={`${match.blind_patient_id}-${match.match_type}-${i}`}>
                    <button
                      className="flex w-full min-h-14 items-start gap-3 border-b border-slate-50 px-3 py-3 text-left active:bg-slate-50 dark:border-slate-800 dark:active:bg-slate-800"
                      disabled={busy}
                      onClick={() => void openPatient(match.blind_patient_id)}
                      type="button"
                    >
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-100 text-sm font-semibold text-teal-900 dark:bg-teal-900/60 dark:text-teal-100">
                        {patientInitials(match.display_name)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                            {match.display_name}
                          </span>
                          <MatchBadge type={match.match_type} />
                        </span>
                        {match.match_type !== "name" ? (
                          <span className="mt-0.5 block text-xs text-slate-600 dark:text-slate-400">
                            <Highlight text={match.match_text} query={query.trim()} />
                          </span>
                        ) : null}
                        <span className="mt-0.5 block text-xs text-slate-400">
                          {match.phone_last4 ? `***${match.phone_last4}` : ""}
                          {match.clinic_mrn ? ` · ${match.clinic_mrn}` : ""}
                          {match.record_date ? ` · ${match.record_date}` : ""}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      ) : (

        /* ── DIRECTORY MODE ── */
        <>
          {dirLoading ? (
            <p className="text-sm text-slate-500">{t("loadingPatients")}</p>
          ) : groups.length === 0 ? (
            <p className="text-center text-sm text-slate-500">{t("noPatientsYet")}</p>
          ) : (
            <div className="pr-6">
              {groups.map((group) => (
                <section
                  key={group.letter}
                  ref={(el) => { sectionRefs.current[group.letter] = el; }}
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
                              {` · ${item.visit_count} ${
                                item.visit_count === 1
                                  ? t("visitOne")
                                  : t("visitMany")
                              }`}
                              {item.last_seen_at ? ` · ${formatIst(item.last_seen_at)}` : ""}
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

          {/* Alphabet fast-scroll rail */}
          {!dirLoading && letters.length > 1 ? (
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
        </>
      )}
    </div>
  );
}
