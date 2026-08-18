export type PatientRow = {
  blind_patient_id: string;
  display_name: string;
  phone_last4: string;
  clinic_mrn: string;
  visit_count: number;
  last_seen_at: string | null;
  has_phone: boolean;
  age_years?: number | null;
};

export type PatientLetterGroup = {
  letter: string;
  items: PatientRow[];
};

function sortLetter(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "#";
  const first = trimmed[0].toUpperCase();
  if (/[A-Z]/.test(first)) return first;
  if (/[0-9]/.test(first)) return "#";
  return "#";
}

/** Group patients A–Z for Pixel Contacts-style list. */
export function groupPatientsByLetter(rows: PatientRow[]): PatientLetterGroup[] {
  const sorted = [...rows].sort((a, b) =>
    a.display_name.localeCompare(b.display_name, "en", { sensitivity: "base" }),
  );
  const map = new Map<string, PatientRow[]>();
  for (const row of sorted) {
    const letter = sortLetter(row.display_name);
    const list = map.get(letter) || [];
    list.push(row);
    map.set(letter, list);
  }
  const letters = [...map.keys()].sort((a, b) => {
    if (a === "#") return 1;
    if (b === "#") return -1;
    return a.localeCompare(b);
  });
  return letters.map((letter) => ({
    letter,
    items: map.get(letter) || [],
  }));
}

export function alphabetIndexLetters(groups: PatientLetterGroup[]): string[] {
  return groups.map((g) => g.letter);
}
