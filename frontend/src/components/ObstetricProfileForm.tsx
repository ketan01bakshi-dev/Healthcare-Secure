"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";
import {
  EMPTY_OBSTETRIC,
  eddFromLmp,
  gestationalAgeAt,
  gplaLabel,
  type ObstetricProfile,
} from "@/lib/obstetric";

const INPUT =
  "mt-1 min-h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none ring-slate-400 focus:ring-2";

/** Obstetric card: LMP, EDD, GPLA, blood group — shown on Patient tab when locked. */
export default function ObstetricProfileForm() {
  const { t } = useI18n();
  const { locked, rawIdentifier, bumpHistory, historyVersion } = usePatient();
  const [profile, setProfile] = useState<ObstetricProfile>(EMPTY_OBSTETRIC);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!locked || !rawIdentifier) {
      setProfile(EMPTY_OBSTETRIC);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch(
          `/api/v1/history/obstetric-profile?raw_identifier=${encodeURIComponent(rawIdentifier)}`,
        );
        if (!res.ok || cancelled) return;
        const text = await res.text();
        if (!text || text === "null") {
          if (!cancelled) setProfile(EMPTY_OBSTETRIC);
          return;
        }
        const data = JSON.parse(text) as Partial<ObstetricProfile>;
        if (cancelled) return;
        setProfile({
          lmp: data.lmp || null,
          edd: data.edd || null,
          edd_source: (data.edd_source as ObstetricProfile["edd_source"]) || "",
          gravida: data.gravida || "",
          para: data.para || "",
          abortions: data.abortions || "",
          living: data.living || "",
          blood_group: data.blood_group || "",
          rh: data.rh || "",
          high_risk_notes: data.high_risk_notes || "",
        });
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locked, rawIdentifier, historyVersion]);

  const ga = useMemo(
    () => gestationalAgeAt(profile.lmp),
    [profile.lmp],
  );

  if (!locked) return null;

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!rawIdentifier) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      let edd = profile.edd || "";
      let eddSource = profile.edd_source;
      if (profile.lmp && !edd) {
        edd = eddFromLmp(profile.lmp) || "";
        eddSource = eddSource || "lmp";
      }
      const res = await apiFetch("/api/v1/history/obstetric-profile", {
        method: "PUT",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          lmp: profile.lmp || "",
          edd,
          edd_source: eddSource,
          gravida: profile.gravida,
          para: profile.para,
          abortions: profile.abortions,
          living: profile.living,
          blood_group: profile.blood_group,
          rh: profile.rh,
          high_risk_notes: profile.high_risk_notes,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as ObstetricProfile;
      setProfile({
        lmp: data.lmp || null,
        edd: data.edd || null,
        edd_source: (data.edd_source as ObstetricProfile["edd_source"]) || "",
        gravida: data.gravida || "",
        para: data.para || "",
        abortions: data.abortions || "",
        living: data.living || "",
        blood_group: data.blood_group || "",
        rh: data.rh || "",
        high_risk_notes: data.high_risk_notes || "",
      });
      setStatus(t("obstetricSaved"));
      bumpHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("obstetricSaveFailed"));
    } finally {
      setBusy(false);
    }
  }

  function setField<K extends keyof ObstetricProfile>(
    key: K,
    value: ObstetricProfile[K],
  ) {
    setProfile((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "lmp" && typeof value === "string" && value) {
        if (!prev.edd || prev.edd_source === "lmp" || !prev.edd_source) {
          next.edd = eddFromLmp(value);
          next.edd_source = "lmp";
        }
      }
      return next;
    });
  }

  return (
    <CollapsibleSection hint={t("obstetricHint")} title={t("obstetricProfile")}>
      {ga ? (
        <p className="text-sm font-medium text-slate-900">
          {t("gestationalAge")}: {ga.label}
          {profile.edd ? ` · EDD ${profile.edd}` : ""}
          {" · "}
          {gplaLabel(profile)}
        </p>
      ) : null}
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={onSave}>
        <label className="text-xs font-medium text-slate-600">
          LMP
          <input
            className={INPUT}
            type="date"
            value={profile.lmp || ""}
            onChange={(e) => setField("lmp", e.target.value || null)}
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          EDD
          <input
            className={INPUT}
            type="date"
            value={profile.edd || ""}
            onChange={(e) => {
              setField("edd", e.target.value || null);
              setField("edd_source", e.target.value ? "usg" : "");
            }}
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          Gravida
          <input
            className={INPUT}
            inputMode="numeric"
            value={profile.gravida}
            onChange={(e) => setField("gravida", e.target.value)}
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          Para
          <input
            className={INPUT}
            inputMode="numeric"
            value={profile.para}
            onChange={(e) => setField("para", e.target.value)}
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          Abortions
          <input
            className={INPUT}
            inputMode="numeric"
            value={profile.abortions}
            onChange={(e) => setField("abortions", e.target.value)}
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          Living
          <input
            className={INPUT}
            inputMode="numeric"
            value={profile.living}
            onChange={(e) => setField("living", e.target.value)}
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          Blood group
          <select
            className={INPUT}
            value={profile.blood_group}
            onChange={(e) => setField("blood_group", e.target.value)}
          >
            <option value="">—</option>
            {["A", "B", "AB", "O"].map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">
          Rh
          <select
            className={INPUT}
            value={profile.rh}
            onChange={(e) => setField("rh", e.target.value)}
          >
            <option value="">—</option>
            <option value="+">Positive</option>
            <option value="-">Negative</option>
          </select>
        </label>
        <label className="sm:col-span-2 text-xs font-medium text-slate-600">
          High-risk notes
          <textarea
            className={`${INPUT} min-h-20 py-2`}
            value={profile.high_risk_notes}
            onChange={(e) => setField("high_risk_notes", e.target.value)}
            maxLength={500}
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="sm:col-span-2 inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : t("saveObstetric")}
        </button>
      </form>
      {error ? (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
      {status ? (
        <p className="mt-2 text-sm text-emerald-800" role="status">
          {status}
        </p>
      ) : null}
    </CollapsibleSection>
  );
}
