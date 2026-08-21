"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { apiFetch } from "@/lib/doctorSession";

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "");
}

function parseAgeYears(value: unknown): string {
  if (value == null || value === "") return "";
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0 || n > 130) return "";
  return String(n);
}

function normalizeMrn(mrn: string): string {
  return mrn.replace(/[^A-Za-z0-9\-]/g, "").toUpperCase();
}

type PatientContextValue = {
  nameDraft: string;
  phoneDraft: string;
  mrnDraft: string;
  abhaDraft: string;
  patientName: string;
  patientPhone: string;
  clinicMrn: string;
  abhaNumber: string;
  rawIdentifier: string;
  blindPatientId: string | null;
  blindPhoneId: string | null;
  locked: boolean;
  patientAgeYears: string;
  setNameDraft: (name: string) => void;
  setPhoneDraft: (phone: string) => void;
  setMrnDraft: (mrn: string) => void;
  setAbhaDraft: (abha: string) => void;
  lockPatient: () => Promise<void>;
  lockFromAppointment: (appointmentId: string) => Promise<string>;
  lockFromDirectory: (blindPatientId: string) => Promise<string>;
  lockFromHandoff: (opts: {
    displayName: string;
    clinicMrn?: string;
    blindPatientId?: string;
  }) => Promise<void>;
  changePatientPhone: (newPhone: string) => Promise<{ recordsMoved: number }>;
  linkAbha: (opts?: {
    txnId?: string;
    linkingToken?: string;
  }) => Promise<string>;
  requestAbhaOtp: () => Promise<{ txn_id: string; message: string }>;
  confirmAbhaOtp: (
    txnId: string,
    otp: string,
  ) => Promise<{ linking_token?: string | null; message?: string }>;
  savePatientAge: (ageYears: string) => Promise<void>;
  selectedDiagnostics: string[];
  dismissedDiagnostics: string[];
  toggleRecommendedDiagnostic: (id: string) => void;
  dismissRecommendedDiagnostic: (id: string) => void;
  clearPatient: () => void;
  historyVersion: number;
  bumpHistory: () => void;
};

const PatientContext = createContext<PatientContextValue | null>(null);

export function PatientProvider({ children }: { children: ReactNode }) {
  const [nameDraft, setNameDraft] = useState("");
  const [phoneDraft, setPhoneDraft] = useState("");
  const [mrnDraft, setMrnDraft] = useState("");
  const [abhaDraft, setAbhaDraft] = useState("");
  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [clinicMrn, setClinicMrn] = useState("");
  const [abhaNumber, setAbhaNumber] = useState("");
  const [rawIdentifier, setRawIdentifier] = useState("");
  const [blindPatientId, setBlindPatientId] = useState<string | null>(null);
  const [blindPhoneId, setBlindPhoneId] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [patientAgeYears, setPatientAgeYears] = useState("");
  const [historyVersion, setHistoryVersion] = useState(0);
  const [selectedDiagnostics, setSelectedDiagnostics] = useState<string[]>([]);
  const [dismissedDiagnostics, setDismissedDiagnostics] = useState<string[]>(
    [],
  );
  const diagnosticsPatientRef = useRef("");
  const ordersReadyRef = useRef(false);
  const skipSaveRef = useRef(true);
  const saveTimerRef = useRef<number | null>(null);

  const bumpHistory = useCallback(() => {
    setHistoryVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    ordersReadyRef.current = false;
  }, [rawIdentifier]);

  useEffect(() => {
    if (!locked || !rawIdentifier) {
      setSelectedDiagnostics([]);
      setDismissedDiagnostics([]);
      diagnosticsPatientRef.current = "";
      ordersReadyRef.current = false;
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch(
          `/api/v1/history/lab-orders?raw_identifier=${encodeURIComponent(rawIdentifier)}`,
        );
        if (cancelled) return;
        if (!res.ok) {
          skipSaveRef.current = true;
          ordersReadyRef.current = true;
          diagnosticsPatientRef.current = rawIdentifier;
          setSelectedDiagnostics([]);
          setDismissedDiagnostics([]);
          return;
        }
        const data = (await res.json()) as {
          selected?: unknown;
          dismissed?: unknown;
        };
        if (cancelled) return;
        const selected = Array.isArray(data.selected)
          ? data.selected.filter((x): x is string => typeof x === "string")
          : [];
        const dismissed = Array.isArray(data.dismissed)
          ? data.dismissed.filter((x): x is string => typeof x === "string")
          : [];
        skipSaveRef.current = true;
        ordersReadyRef.current = true;
        diagnosticsPatientRef.current = rawIdentifier;
        setSelectedDiagnostics(selected);
        setDismissedDiagnostics(dismissed);
      } catch {
        if (!cancelled) {
          skipSaveRef.current = true;
          ordersReadyRef.current = true;
          diagnosticsPatientRef.current = rawIdentifier;
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locked, rawIdentifier, historyVersion]);

  useEffect(() => {
    if (!locked || !rawIdentifier || !ordersReadyRef.current) return;
    if (diagnosticsPatientRef.current !== rawIdentifier) return;
    if (skipSaveRef.current) {
      skipSaveRef.current = false;
      return;
    }
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      void apiFetch("/api/v1/history/lab-orders", {
        method: "PUT",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          selected: selectedDiagnostics,
          dismissed: dismissedDiagnostics,
        }),
      });
    }, 400);
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, [selectedDiagnostics, dismissedDiagnostics, locked, rawIdentifier]);

  useEffect(() => {
    if (!locked) return;
    const tick = () => {
      if (document.visibilityState !== "visible") return;
      bumpHistory();
    };
    const id = window.setInterval(tick, 15000);
    const onVis = () => {
      if (document.visibilityState === "visible") bumpHistory();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [locked, bumpHistory]);

  const toggleRecommendedDiagnostic = useCallback((id: string) => {
    setSelectedDiagnostics((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const dismissRecommendedDiagnostic = useCallback((id: string) => {
    setDismissedDiagnostics((prev) =>
      prev.includes(id) ? prev : [...prev, id],
    );
    setSelectedDiagnostics((prev) => prev.filter((x) => x !== id));
  }, []);

  const lockPatient = useCallback(async () => {
    const name = nameDraft.trim();
    const phone = phoneDraft.trim();
    const digits = digitsOnly(phone);
    const mrn = normalizeMrn(mrnDraft);
    if (!name) {
      throw new Error("Enter the patient name first.");
    }
    if (!mrn && (!digits || digits.length !== 10)) {
      throw new Error("Enter a 10-digit mobile, or a clinic MRN.");
    }
    if (mrn && digits && digits.length !== 10 && digits.length > 0) {
      throw new Error("Mobile must be exactly 10 digits when provided.");
    }
    const response = await apiFetch("/api/v1/history/tokenize", {
      method: "POST",
      body: JSON.stringify({
        patient_name: name,
        patient_phone: digits || undefined,
        clinic_mrn: mrn || undefined,
      }),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(
        text || `Could not encode patient identity (${response.status})`,
      );
    }
    const data = (await response.json()) as {
      blind_patient_id?: string;
      blind_phone_id?: string | null;
      clinic_mrn?: string | null;
      raw_identifier_shape?: string;
      age_years?: number | null;
    };
    if (!data.blind_patient_id) {
      throw new Error("Could not select patient. Please try again.");
    }
    const issuedMrn = normalizeMrn(data.clinic_mrn || mrn || "");
    if (!issuedMrn) {
      throw new Error("Clinic MRN was not issued. Please try again.");
    }
    setPatientName(name);
    setPatientPhone(digits);
    setClinicMrn(issuedMrn);
    setMrnDraft(issuedMrn);
    setAbhaNumber(digitsOnly(abhaDraft));
    setRawIdentifier(`mrn|${issuedMrn}`);
    setBlindPatientId(data.blind_patient_id);
    setBlindPhoneId(data.blind_phone_id ?? null);
    setPatientAgeYears(parseAgeYears(data.age_years));
    setLocked(true);
    setHistoryVersion((v) => v + 1);
  }, [nameDraft, phoneDraft, mrnDraft, abhaDraft]);

  const lockFromAppointment = useCallback(async (appointmentId: string) => {
    const idRes = await apiFetch(
      `/api/v1/appointments/${appointmentId}/patient-identity`,
    );
    if (!idRes.ok) {
      const text = await idRes.text().catch(() => "");
      let detail = text || `Could not load appointment (${idRes.status})`;
      try {
        const parsed = JSON.parse(text) as { detail?: string };
        if (typeof parsed.detail === "string") detail = parsed.detail;
      } catch {
        /* keep */
      }
      throw new Error(detail);
    }
    const identity = (await idRes.json()) as {
      display_name?: string;
      phone?: string;
    };
    const name = (identity.display_name || "").trim();
    const digits = digitsOnly(identity.phone || "");
    if (!name) {
      throw new Error("Appointment has no patient name.");
    }
    if (digits.length !== 10) {
      throw new Error("Appointment phone is not a valid 10-digit mobile.");
    }
    const response = await apiFetch("/api/v1/history/tokenize", {
      method: "POST",
      body: JSON.stringify({
        patient_name: name,
        patient_phone: digits,
      }),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(
        text || `Could not encode patient identity (${response.status})`,
      );
    }
    const data = (await response.json()) as {
      blind_patient_id?: string;
      blind_phone_id?: string | null;
      clinic_mrn?: string | null;
      age_years?: number | null;
    };
    if (!data.blind_patient_id) {
      throw new Error("Could not select patient. Please try again.");
    }
    const issuedMrn = normalizeMrn(data.clinic_mrn || "");
    if (!issuedMrn) {
      throw new Error("Clinic MRN was not issued. Please try again.");
    }
    setNameDraft(name);
    setPhoneDraft(digits);
    setMrnDraft(issuedMrn);
    setPatientName(name);
    setPatientPhone(digits);
    setClinicMrn(issuedMrn);
    setRawIdentifier(`mrn|${issuedMrn}`);
    setBlindPatientId(data.blind_patient_id);
    setBlindPhoneId(data.blind_phone_id ?? null);
    setPatientAgeYears(parseAgeYears(data.age_years));
    setLocked(true);
    setHistoryVersion((v) => v + 1);
    return data.blind_patient_id;
  }, []);

  const lockFromDirectory = useCallback(async (blindPatientId: string) => {
    const idRes = await apiFetch(
      `/api/v1/history/patients/${encodeURIComponent(blindPatientId)}/identity`,
    );
    if (!idRes.ok) {
      const text = await idRes.text().catch(() => "");
      let detail = text || `Could not load patient (${idRes.status})`;
      try {
        const parsed = JSON.parse(text) as { detail?: string };
        if (typeof parsed.detail === "string") detail = parsed.detail;
      } catch {
        /* keep */
      }
      throw new Error(detail);
    }
    const identity = (await idRes.json()) as {
      display_name?: string;
      phone?: string;
      clinic_mrn?: string;
    };
    const name = (identity.display_name || "").trim();
    const digits = digitsOnly(identity.phone || "");
    const mrn = normalizeMrn(identity.clinic_mrn || "");
    if (!name) {
      throw new Error("Patient has no name on file.");
    }
    if (!mrn && digits.length !== 10) {
      throw new Error("Patient phone is not a valid 10-digit mobile.");
    }
    const response = await apiFetch("/api/v1/history/tokenize", {
      method: "POST",
      body: JSON.stringify({
        patient_name: name,
        patient_phone: digits || undefined,
        clinic_mrn: mrn || undefined,
      }),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(
        text || `Could not encode patient identity (${response.status})`,
      );
    }
    const data = (await response.json()) as {
      blind_patient_id?: string;
      blind_phone_id?: string | null;
      clinic_mrn?: string | null;
      age_years?: number | null;
    };
    if (!data.blind_patient_id) {
      throw new Error("Could not select patient. Please try again.");
    }
    const issuedMrn = normalizeMrn(data.clinic_mrn || mrn || "");
    if (!issuedMrn) {
      throw new Error("Clinic MRN was not issued. Please try again.");
    }
    setNameDraft(name);
    setPhoneDraft(digits);
    setMrnDraft(issuedMrn);
    setPatientName(name);
    setPatientPhone(digits);
    setClinicMrn(issuedMrn);
    setRawIdentifier(`mrn|${issuedMrn}`);
    setBlindPatientId(data.blind_patient_id);
    setBlindPhoneId(data.blind_phone_id ?? null);
    setPatientAgeYears(parseAgeYears(data.age_years));
    setLocked(true);
    setHistoryVersion((v) => v + 1);
    return data.blind_patient_id;
  }, []);

  const lockFromHandoff = useCallback(
    async (opts: {
      displayName: string;
      clinicMrn?: string;
      blindPatientId?: string;
    }) => {
      const name = (opts.displayName || "").trim();
      const mrn = normalizeMrn(opts.clinicMrn || "");
      if (!name) {
        throw new Error("Handoff has no patient name.");
      }
      if (mrn) {
        const response = await apiFetch("/api/v1/history/tokenize", {
          method: "POST",
          body: JSON.stringify({
            patient_name: name,
            clinic_mrn: mrn,
          }),
        });
        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(
            text || `Could not open patient (${response.status})`,
          );
        }
        const data = (await response.json()) as {
          blind_patient_id?: string;
          blind_phone_id?: string | null;
          clinic_mrn?: string | null;
          age_years?: number | null;
        };
        if (!data.blind_patient_id) {
          throw new Error("Could not select patient. Please try again.");
        }
        const issuedMrn = normalizeMrn(data.clinic_mrn || mrn);
        setNameDraft(name);
        setMrnDraft(issuedMrn);
        setPatientName(name);
        setClinicMrn(issuedMrn);
        setRawIdentifier(`mrn|${issuedMrn}`);
        setBlindPatientId(data.blind_patient_id);
        setBlindPhoneId(data.blind_phone_id ?? null);
        setPatientAgeYears(parseAgeYears(data.age_years));
        setLocked(true);
        setHistoryVersion((v) => v + 1);
        return;
      }
      if (opts.blindPatientId) {
        await lockFromDirectory(opts.blindPatientId);
        return;
      }
      throw new Error("Handoff has no MRN or patient id to open.");
    },
    [lockFromDirectory],
  );

  const changePatientPhone = useCallback(
    async (newPhone: string) => {
      if (!locked || !patientName.trim()) {
        throw new Error("Select a patient first.");
      }
      const newDigits = digitsOnly(newPhone);
      if (newDigits.length !== 10) {
        throw new Error("New mobile number must be exactly 10 digits.");
      }
      if (newDigits === patientPhone) {
        throw new Error("New mobile number is the same as the current one.");
      }
      const response = await apiFetch("/api/v1/history/change-phone", {
        method: "POST",
        body: JSON.stringify({
          patient_name: patientName.trim(),
          old_phone: patientPhone || "0000000000",
          new_phone: newDigits,
          clinic_mrn: clinicMrn || undefined,
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        let detail = text || `Could not update mobile (${response.status})`;
        try {
          const parsed = JSON.parse(text) as { detail?: string };
          if (typeof parsed.detail === "string") detail = parsed.detail;
        } catch {
          /* keep */
        }
        throw new Error(detail);
      }
      const data = (await response.json()) as {
        blind_patient_id?: string;
        blind_phone_id?: string | null;
        new_phone_digits?: string;
        records_moved?: number;
        clinic_mrn?: string | null;
      };
      if (!data.blind_patient_id || !data.new_phone_digits) {
        throw new Error("Could not update mobile. Please try again.");
      }
      const digits = data.new_phone_digits;
      const issuedMrn = normalizeMrn(data.clinic_mrn || clinicMrn || "");
      setPatientPhone(digits);
      setPhoneDraft(digits);
      if (issuedMrn) {
        setClinicMrn(issuedMrn);
        setMrnDraft(issuedMrn);
        setRawIdentifier(`mrn|${issuedMrn}`);
      }
      setBlindPatientId(data.blind_patient_id);
      setBlindPhoneId(data.blind_phone_id ?? null);
      setHistoryVersion((v) => v + 1);
      return { recordsMoved: data.records_moved ?? 0 };
    },
    [locked, patientName, patientPhone, clinicMrn],
  );

  const linkAbha = useCallback(
    async (opts?: { txnId?: string; linkingToken?: string }) => {
      if (!locked || !rawIdentifier) {
        throw new Error("Select a patient first.");
      }
      const abha = (abhaDraft || abhaNumber).trim();
      const digits = digitsOnly(abha);
      if (digits.length < 8 && !abha.includes("@")) {
        throw new Error("Enter a valid ABHA number or address.");
      }
      const response = await apiFetch("/api/v1/integrations/abha/link", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          abha_number: abha,
          consent_acknowledged: true,
          txn_id: opts?.txnId || undefined,
          linking_token: opts?.linkingToken || undefined,
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || "Could not link ABHA");
      }
      setAbhaNumber(digits.length >= 8 ? digits : abha);
      setHistoryVersion((v) => v + 1);
      const data = (await response.json()) as { message?: string };
      return data.message || "ABHA linked.";
    },
    [locked, rawIdentifier, abhaDraft, abhaNumber],
  );

  const requestAbhaOtp = useCallback(async () => {
    const abha = (abhaDraft || abhaNumber).trim();
    if (!abha) throw new Error("Enter ABHA number or address first.");
    const response = await apiFetch("/api/v1/integrations/abha/otp/request", {
      method: "POST",
      body: JSON.stringify({ abha_address_or_number: abha }),
    });
    if (!response.ok) {
      throw new Error((await response.text()) || "OTP request failed");
    }
    const data = (await response.json()) as {
      txn_id?: string;
      message?: string;
    };
    if (!data.txn_id) throw new Error("No txn_id from ABDM");
    return { txn_id: data.txn_id, message: data.message || "OTP sent" };
  }, [abhaDraft, abhaNumber]);

  const confirmAbhaOtp = useCallback(async (txnId: string, otp: string) => {
    const response = await apiFetch("/api/v1/integrations/abha/otp/confirm", {
      method: "POST",
      body: JSON.stringify({ txn_id: txnId, otp }),
    });
    if (!response.ok) {
      throw new Error((await response.text()) || "OTP confirm failed");
    }
    const data = (await response.json()) as {
      linking_token?: string | null;
      status?: string;
      message?: string;
    };
    return {
      linking_token: data.linking_token,
      message: data.message || data.status,
    };
  }, []);

  const savePatientAge = useCallback(
    async (ageYears: string) => {
      if (!locked || !rawIdentifier) {
        throw new Error("Select a patient first.");
      }
      const trimmed = ageYears.trim();
      let age: number | null = null;
      if (trimmed !== "") {
        age = Number.parseFloat(trimmed);
        if (!Number.isFinite(age) || age < 0 || age > 130) {
          throw new Error("Age must be between 0 and 130 years.");
        }
      }
      const response = await apiFetch("/api/v1/history/patient-age", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          age_years: age,
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || "Could not save age.");
      }
      const data = (await response.json()) as { age_years?: number | null };
      setPatientAgeYears(parseAgeYears(data.age_years));
    },
    [locked, rawIdentifier],
  );

  const clearPatient = useCallback(() => {
    setNameDraft("");
    setPhoneDraft("");
    setMrnDraft("");
    setAbhaDraft("");
    setPatientName("");
    setPatientPhone("");
    setClinicMrn("");
    setAbhaNumber("");
    setRawIdentifier("");
    setBlindPatientId(null);
    setBlindPhoneId(null);
    setPatientAgeYears("");
    setLocked(false);
    setSelectedDiagnostics([]);
    setDismissedDiagnostics([]);
    diagnosticsPatientRef.current = "";
    ordersReadyRef.current = false;
    skipSaveRef.current = true;
    setHistoryVersion((v) => v + 1);
  }, []);

  const value = useMemo(
    () => ({
      nameDraft,
      phoneDraft,
      mrnDraft,
      abhaDraft,
      patientName,
      patientPhone,
      clinicMrn,
      abhaNumber,
      rawIdentifier,
      blindPatientId,
      blindPhoneId,
      locked,
      patientAgeYears,
      setNameDraft,
      setPhoneDraft,
      setMrnDraft,
      setAbhaDraft,
      lockPatient,
      lockFromAppointment,
      lockFromDirectory,
      lockFromHandoff,
      changePatientPhone,
      linkAbha,
      requestAbhaOtp,
      confirmAbhaOtp,
      savePatientAge,
      selectedDiagnostics,
      dismissedDiagnostics,
      toggleRecommendedDiagnostic,
      dismissRecommendedDiagnostic,
      clearPatient,
      historyVersion,
      bumpHistory,
    }),
    [
      nameDraft,
      phoneDraft,
      mrnDraft,
      abhaDraft,
      patientName,
      patientPhone,
      clinicMrn,
      abhaNumber,
      rawIdentifier,
      blindPatientId,
      blindPhoneId,
      locked,
      patientAgeYears,
      lockPatient,
      lockFromAppointment,
      lockFromDirectory,
      lockFromHandoff,
      changePatientPhone,
      linkAbha,
      requestAbhaOtp,
      confirmAbhaOtp,
      savePatientAge,
      selectedDiagnostics,
      dismissedDiagnostics,
      toggleRecommendedDiagnostic,
      dismissRecommendedDiagnostic,
      clearPatient,
      historyVersion,
      bumpHistory,
    ],
  );

  return (
    <PatientContext.Provider value={value}>{children}</PatientContext.Provider>
  );
}

export function usePatient() {
  const ctx = useContext(PatientContext);
  if (!ctx) {
    throw new Error("usePatient must be used within PatientProvider");
  }
  return ctx;
}
