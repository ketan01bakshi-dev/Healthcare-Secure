"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import CollapsibleSection from "@/components/CollapsibleSection";
import { useActiveClinicRole } from "@/components/DoctorGate";
import { usePatient } from "@/context/PatientContext";
import { downloadIcs, openGoogleCalendar } from "@/lib/calendarExport";
import { formatIst, parseApiDate } from "@/lib/datetimeIst";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "").slice(0, 14);
}

function toDatetimeLocalValue(iso: string): string {
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function PatientBar() {
  const {
    abhaDraft,
    patientName,
    patientPhone,
    clinicMrn,
    abhaNumber,
    rawIdentifier,
    locked,
    patientAgeYears,
    savePatientAge,
    setAbhaDraft,
    changePatientPhone,
    linkAbha,
    requestAbhaOtp,
    confirmAbhaOtp,
    clearPatient,
  } = usePatient();
  const { t } = useI18n();
  const router = useRouter();
  const role = useActiveClinicRole();
  const isLab = role === "lab";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [editingPhone, setEditingPhone] = useState(false);
  const [newPhoneDraft, setNewPhoneDraft] = useState("");
  const [abhaTxnId, setAbhaTxnId] = useState<string | null>(null);
  const [abhaOtp, setAbhaOtp] = useState("");
  const [nextWhen, setNextWhen] = useState("");
  const [savedNextIso, setSavedNextIso] = useState<string | null>(null);
  const [ageDraft, setAgeDraft] = useState("");

  useEffect(() => {
    setAgeDraft(patientAgeYears);
  }, [patientAgeYears, locked]);

  async function onChangePhone(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const result = await changePatientPhone(newPhoneDraft);
      setEditingPhone(false);
      setNewPhoneDraft("");
      setStatus(
        result.recordsMoved > 0
          ? `Mobile updated. ${result.recordsMoved} past visit(s) kept.`
          : "Mobile updated.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update mobile.");
    } finally {
      setBusy(false);
    }
  }

  const newDigitCount = useMemo(
    () => newPhoneDraft.replace(/\D+/g, "").length,
    [newPhoneDraft],
  );
  const canChangePhone =
    newDigitCount === 10 && newPhoneDraft !== patientPhone;

  useEffect(() => {
    if (!locked || !rawIdentifier || isLab) {
      setNextWhen("");
      setSavedNextIso(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch(
          `/api/v1/appointments/next?raw_identifier=${encodeURIComponent(rawIdentifier)}`,
        );
        if (!res.ok || cancelled) return;
        const text = await res.text();
        if (!text || text === "null") {
          if (!cancelled) {
            setNextWhen("");
            setSavedNextIso(null);
          }
          return;
        }
        const data = JSON.parse(text) as { scheduled_at?: string | null };
        if (cancelled) return;
        if (data.scheduled_at) {
          setSavedNextIso(data.scheduled_at);
          setNextWhen(toDatetimeLocalValue(data.scheduled_at));
        } else {
          setSavedNextIso(null);
          setNextWhen("");
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locked, rawIdentifier, isLab]);

  async function onSaveNextAppointment(event: FormEvent) {
    event.preventDefault();
    if (!locked || !rawIdentifier) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const digits = digitsOnly(patientPhone);
      if (digits.length !== 10) {
        throw new Error(t("mobileRequired10"));
      }
      if (!nextWhen) {
        throw new Error(t("appointmentWhenRequired"));
      }
      const whenIso = new Date(nextWhen).toISOString();
      const res = await apiFetch("/api/v1/appointments/next", {
        method: "POST",
        body: JSON.stringify({
          display_name: patientName,
          raw_identifier: rawIdentifier,
          phone: digits,
          scheduled_at: whenIso,
          reason: "Next appointment",
          send_sms: false,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { scheduled_at?: string };
      const iso = data.scheduled_at || whenIso;
      setSavedNextIso(iso);
      setStatus(t("nextAppointmentSaved"));
      window.dispatchEvent(new Event("healthcare-appointments-changed"));
      const ev = {
        title: `Clinic: ${patientName}`,
        startIso: iso,
        durationMinutes: 15,
        description: "Next appointment",
      };
      downloadIcs(ev, `next-${patientName.replace(/\s+/g, "-")}.ics`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("nextAppointmentFailed"),
      );
    } finally {
      setBusy(false);
    }
  }

  if (!locked) {
    return null;
  }

  return (
    <CollapsibleSection
      aria-label="Patient identity"
      className="w-full overflow-x-hidden rounded-xl border border-slate-200 bg-white px-4 py-4"
      hint={t("patientHint")}
      title={t("patient")}
    >
      <div className="mt-4 space-y-3">
          <p className="text-base font-medium text-slate-900">{patientName}</p>
          {patientPhone ? (
            <p className="text-sm text-slate-700">Mobile: {patientPhone}</p>
          ) : null}
          {clinicMrn ? (
            <p className="text-sm text-slate-700">MRN: {clinicMrn}</p>
          ) : null}
          {abhaNumber ? (
            <p className="text-sm text-slate-700">ABHA: {abhaNumber}</p>
          ) : null}

          {editingPhone ? (
            <form className="space-y-3" onSubmit={onChangePhone}>
              <input
                aria-label="New mobile"
                className="min-h-12 w-full rounded-lg border border-slate-200 bg-white px-4 text-sm"
                inputMode="numeric"
                maxLength={14}
                onChange={(e) =>
                  setNewPhoneDraft(digitsOnly(e.target.value).slice(0, 10))
                }
                placeholder="New 10-digit mobile"
                value={newPhoneDraft}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  className="min-h-12 rounded-lg bg-clinical-500 px-4 text-sm text-white disabled:opacity-60"
                  disabled={busy || !canChangePhone}
                  type="submit"
                >
                  Save new mobile
                </button>
                <button
                  className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                  onClick={() => setEditingPhone(false)}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <div className="flex flex-wrap gap-2">
              {!isLab ? (
                <>
                  <button
                    className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                    onClick={() => setEditingPhone(true)}
                    type="button"
                  >
                    {t("updateMobile")}
                  </button>
                  <button
                    className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                    disabled={busy || !(abhaDraft || abhaNumber).trim()}
                    onClick={() => {
                      void (async () => {
                        setBusy(true);
                        setError(null);
                        try {
                          const r = await requestAbhaOtp();
                          setAbhaTxnId(r.txn_id);
                          setStatus(r.message);
                        } catch (err) {
                          setError(
                            err instanceof Error
                              ? err.message
                              : "ABHA OTP failed",
                          );
                        } finally {
                          setBusy(false);
                        }
                      })();
                    }}
                    type="button"
                  >
                    {t("abhaRequestOtp")}
                  </button>
                  {abhaTxnId ? (
                    <div className="flex w-full flex-wrap items-end gap-2">
                      <label className="text-xs text-slate-600">
                        OTP
                        <input
                          className="mt-1 min-h-12 rounded-lg border border-slate-200 px-3 text-sm"
                          value={abhaOtp}
                          onChange={(e) => setAbhaOtp(e.target.value)}
                          inputMode="numeric"
                          placeholder="123456"
                        />
                      </label>
                      <button
                        className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                        disabled={busy || abhaOtp.length < 4}
                        type="button"
                        onClick={() => {
                          void (async () => {
                            setBusy(true);
                            setError(null);
                            try {
                              const conf = await confirmAbhaOtp(
                                abhaTxnId,
                                abhaOtp,
                              );
                              const msg = await linkAbha({
                                txnId: abhaTxnId,
                                linkingToken: conf.linking_token || undefined,
                              });
                              setStatus(msg);
                              setAbhaTxnId(null);
                              setAbhaOtp("");
                            } catch (err) {
                              setError(
                                err instanceof Error
                                  ? err.message
                                  : "ABHA confirm failed",
                              );
                            } finally {
                              setBusy(false);
                            }
                          })();
                        }}
                      >
                        {t("abhaConfirmLink")}
                      </button>
                    </div>
                  ) : (
                    <button
                      className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                      disabled={
                        busy ||
                        digitsOnly(abhaDraft || abhaNumber).length < 8
                      }
                      onClick={() => {
                        void (async () => {
                          setBusy(true);
                          setError(null);
                          try {
                            const msg = await linkAbha();
                            setStatus(msg);
                          } catch (err) {
                            setError(
                              err instanceof Error
                                ? err.message
                                : "ABHA link failed",
                            );
                          } finally {
                            setBusy(false);
                          }
                        })();
                      }}
                      type="button"
                    >
                      {t("abhaLinkLocal")}
                    </button>
                  )}
                </>
              ) : null}
              <button
                className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                onClick={() => {
                  clearPatient();
                  router.push("/home/patients/");
                }}
                type="button"
              >
                {t("changePatient")}
              </button>
            </div>
          )}

          {!isLab ? (
            <>
              <form
                className="mt-4 space-y-2 border-t border-slate-100 pt-4"
                onSubmit={async (event) => {
                  event.preventDefault();
                  setBusy(true);
                  setError(null);
                  setStatus(null);
                  try {
                    await savePatientAge(ageDraft);
                    setStatus(t("patientAgeSaved"));
                  } catch (err) {
                    setError(
                      err instanceof Error ? err.message : t("patientAgeFailed"),
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {t("patientAge")}
                </h3>
                <p className="text-sm text-slate-600">{t("patientAgeHint")}</p>
                <input
                  aria-label={t("patientAge")}
                  className="min-h-12 w-full rounded-lg border border-slate-200 bg-white px-4 text-sm outline-none ring-clinical-500 focus:ring-2"
                  disabled={busy}
                  inputMode="decimal"
                  onChange={(e) => setAgeDraft(e.target.value)}
                  placeholder="e.g. 32"
                  value={ageDraft}
                />
                <button
                  className="inline-flex min-h-12 items-center justify-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-800 disabled:opacity-60"
                  disabled={busy}
                  type="submit"
                >
                  {busy ? "Please wait…" : t("savePatientAge")}
                </button>
              </form>
            <form
              className="mt-4 space-y-2 border-t border-slate-100 pt-4"
              onSubmit={onSaveNextAppointment}
            >
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t("nextAppointment")}
              </h3>
              <p className="text-sm text-slate-600">{t("nextAppointmentHint")}</p>
              {savedNextIso ? (
                <p className="text-xs text-slate-500">
                  {formatIst(savedNextIso)}
                </p>
              ) : null}
              <input
                aria-label={t("nextAppointment")}
                className="min-h-12 w-full rounded-lg border border-slate-200 bg-white px-4 text-sm outline-none ring-clinical-500 focus:ring-2"
                onChange={(e) => setNextWhen(e.target.value)}
                required
                type="datetime-local"
                value={nextWhen}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60"
                  disabled={busy || !nextWhen || digitsOnly(patientPhone).length !== 10}
                  type="submit"
                >
                  {busy ? "Please wait…" : t("saveNextAppointment")}
                </button>
                {savedNextIso ? (
                  <>
                    <button
                      className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                      onClick={() =>
                        openGoogleCalendar({
                          title: `Clinic: ${patientName}`,
                          startIso: savedNextIso,
                          durationMinutes: 15,
                          description: "Next appointment",
                        })
                      }
                      type="button"
                    >
                      {t("addToGoogleCalendar")}
                    </button>
                    <button
                      className="min-h-12 rounded-lg border border-slate-200 px-4 text-sm"
                      onClick={() =>
                        downloadIcs({
                          title: `Clinic: ${patientName}`,
                          startIso: savedNextIso,
                          durationMinutes: 15,
                          description: "Next appointment",
                        })
                      }
                      type="button"
                    >
                      {t("downloadIcs")}
                    </button>
                  </>
                ) : null}
              </div>
            </form>
            </>
          ) : null}
      </div>

      {error ? (
        <p className="mt-3 text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
      {status ? (
        <p className="mt-3 text-sm text-slate-700" role="status">
          {status}
        </p>
      ) : null}
    </CollapsibleSection>
  );
}
