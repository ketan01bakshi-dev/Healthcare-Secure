/** Physiological range checks for clinic vitals (adult outpatient). Empty = OK. */

export type VitalsFields = {
  blood_pressure: string;
  pulse: string;
  temperature: string;
  spo2: string;
  weight: string;
  height: string;
  respiratory_rate: string;
  hemoglobin: string;
};

export type VitalsFieldKey = keyof VitalsFields;

const NOTES_MAX = 2000;

function parseNumber(raw: string): number | null {
  const cleaned = raw.trim().replace(",", ".");
  if (!cleaned) return null;
  const n = Number(cleaned);
  if (!Number.isFinite(n)) return null;
  return n;
}

function inRange(n: number, min: number, max: number): boolean {
  return n >= min && n <= max;
}

export function validateBloodPressure(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const match = /^(\d{2,3})\s*\/\s*(\d{2,3})$/.exec(value);
  if (!match) {
    return "Enter BP as 120/80 (mmHg)";
  }
  const systolic = Number(match[1]);
  const diastolic = Number(match[2]);
  if (!inRange(systolic, 70, 250) || !inRange(diastolic, 40, 150)) {
    return "Blood pressure must be between 70/40 and 250/150";
  }
  if (systolic <= diastolic) {
    return "Systolic must be higher than diastolic";
  }
  return null;
}

export function validatePulse(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const n = parseNumber(value);
  if (n === null || !Number.isInteger(n)) {
    return "Pulse must be a whole number (bpm)";
  }
  if (!inRange(n, 30, 220)) {
    return "Pulse must be 30–220";
  }
  return null;
}

export function validateTemperature(
  raw: string,
  unit: "F" | "C" = "F",
): string | null {
  const value = raw.trim();
  if (!value) return null;
  const n = parseNumber(value);
  if (n === null) {
    return "Enter temperature as a number";
  }
  if (unit === "C") {
    if (!inRange(n, 34, 42.5)) {
      return "Temperature must be 34–42.5 °C";
    }
    return null;
  }
  if (!inRange(n, 93, 108)) {
    return "Temperature must be 93–108 °F";
  }
  return null;
}

export function validateSpo2(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const n = parseNumber(value.replace(/%$/, ""));
  if (n === null) {
    return "Enter SpO₂ as a number";
  }
  if (!inRange(n, 50, 100)) {
    return "SpO₂ must be 50–100";
  }
  return null;
}

export function validateWeight(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const n = parseNumber(value);
  if (n === null) {
    return "Enter weight in kg";
  }
  if (!inRange(n, 1, 300)) {
    return "Weight must be 1–300 kg";
  }
  return null;
}

export function validateHeight(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const n = parseNumber(value);
  if (n === null) {
    return "Enter height in cm";
  }
  if (!inRange(n, 40, 250)) {
    return "Height must be 40–250 cm";
  }
  return null;
}

export function validateRespiratoryRate(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const n = parseNumber(value);
  if (n === null || !Number.isInteger(n)) {
    return "Respiratory rate must be a whole number";
  }
  if (!inRange(n, 5, 60)) {
    return "Respiratory rate must be 5–60";
  }
  return null;
}

export function validateHemoglobin(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const n = parseNumber(value);
  if (n === null) {
    return "Enter hemoglobin in g/dL";
  }
  if (!inRange(n, 3, 22)) {
    return "Hemoglobin must be 3–22 g/dL";
  }
  return null;
}

export function validateNotes(raw: string): string | null {
  if (raw.length > NOTES_MAX) {
    return "Notes are too long";
  }
  return null;
}

const FIELD_VALIDATORS: Record<
  VitalsFieldKey,
  (raw: string) => string | null
> = {
  blood_pressure: validateBloodPressure,
  pulse: validatePulse,
  temperature: (raw) => validateTemperature(raw, "F"),
  spo2: validateSpo2,
  weight: validateWeight,
  height: validateHeight,
  respiratory_rate: validateRespiratoryRate,
  hemoglobin: validateHemoglobin,
};

export function validateVitalField(
  key: VitalsFieldKey,
  raw: string,
  opts?: { temperatureUnit?: "F" | "C" },
): string | null {
  if (key === "temperature") {
    return validateTemperature(raw, opts?.temperatureUnit ?? "F");
  }
  return FIELD_VALIDATORS[key](raw);
}

export function validateAllVitals(
  vitals: VitalsFields,
  notes: string,
  opts?: { temperatureUnit?: "F" | "C" },
): Partial<Record<VitalsFieldKey | "notes", string>> {
  const errors: Partial<Record<VitalsFieldKey | "notes", string>> = {};
  for (const key of Object.keys(FIELD_VALIDATORS) as VitalsFieldKey[]) {
    const err = validateVitalField(key, vitals[key], opts);
    if (err) errors[key] = err;
  }
  const notesErr = validateNotes(notes);
  if (notesErr) errors.notes = notesErr;
  return errors;
}

export function hasVitalsErrors(
  errors: Partial<Record<VitalsFieldKey | "notes", string>>,
): boolean {
  return Object.keys(errors).length > 0;
}

export function hasAnyVitalOrNotes(
  vitals: VitalsFields,
  notes: string,
): boolean {
  if (notes.trim()) return true;
  return Object.values(vitals).some((v) => v.trim().length > 0);
}
