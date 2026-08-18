"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiFetch } from "@/lib/doctorSession";

function digitsOnly(phone: string): string {
  return phone.replace(/\D+/g, "");
}

type PatientContextValue = {
  nameDraft: string;
  phoneDraft: string;
  patientName: string;
  /** Clear-text phone digits kept in memory only for SMS share. */
  patientPhone: string;
  /** Composite `name|digits` used for HMAC history linkage. */
  rawIdentifier: string;
  blindPatientId: string | null;
  blindPhoneId: string | null;
  locked: boolean;
  setNameDraft: (name: string) => void;
  setPhoneDraft: (phone: string) => void;
  lockPatient: () => Promise<void>;
  selectPatient: (name: string, phone: string) => Promise<void>;
  clearPatient: () => void;
  historyVersion: number;
  bumpHistory: () => void;
};

const PatientContext = createContext<PatientContextValue | null>(null);

export function PatientProvider({ children }: { children: ReactNode }) {
  const [nameDraft, setNameDraft] = useState("");
  const [phoneDraft, setPhoneDraft] = useState("");
  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [rawIdentifier, setRawIdentifier] = useState("");
  const [blindPatientId, setBlindPatientId] = useState<string | null>(null);
  const [blindPhoneId, setBlindPhoneId] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [historyVersion, setHistoryVersion] = useState(0);

  const selectPatient = useCallback(async (nameInput: string, phoneInput: string) => {
    const name = nameInput.trim();
    const phone = phoneInput.trim();
    const digits = digitsOnly(phone);
    if (!name) {
      throw new Error("Enter the patient name first.");
    }
    if (!digits || digits.length !== 10) {
      throw new Error("Patient phone must be exactly 10 digits.");
    }
    const response = await apiFetch("/api/v1/history/tokenize", {
      method: "POST",
      body: JSON.stringify({
        patient_name: name,
        patient_phone: phone,
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
    };
    if (!data.blind_patient_id) {
      throw new Error("Could not select patient. Please try again.");
    }
    setPatientName(name);
    setPatientPhone(digits);
    setRawIdentifier(`${name}|${digits}`);
    setBlindPatientId(data.blind_patient_id);
    setBlindPhoneId(data.blind_phone_id ?? null);
    setLocked(true);
    setHistoryVersion((v) => v + 1);
  }, []);

  const lockPatient = useCallback(async () => {
    await selectPatient(nameDraft, phoneDraft);
  }, [nameDraft, phoneDraft]);

  const clearPatient = useCallback(() => {
    setNameDraft("");
    setPhoneDraft("");
    setPatientName("");
    setPatientPhone("");
    setRawIdentifier("");
    setBlindPatientId(null);
    setBlindPhoneId(null);
    setLocked(false);
    setHistoryVersion((v) => v + 1);
  }, []);

  const bumpHistory = useCallback(() => {
    setHistoryVersion((v) => v + 1);
  }, []);

  const value = useMemo(
    () => ({
      nameDraft,
      phoneDraft,
      patientName,
      patientPhone,
      rawIdentifier,
      blindPatientId,
      blindPhoneId,
      locked,
      setNameDraft,
      setPhoneDraft,
      lockPatient,
      selectPatient,
      clearPatient,
      historyVersion,
      bumpHistory,
    }),
    [
      nameDraft,
      phoneDraft,
      patientName,
      patientPhone,
      rawIdentifier,
      blindPatientId,
      blindPhoneId,
      locked,
      lockPatient,
      selectPatient,
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
