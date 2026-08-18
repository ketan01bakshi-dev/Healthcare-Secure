export type RecommendedDiagnostic = {
  id: string;
  label: string;
};

/** प्रमुख जांचें — Alpha Clinic (obstetric) visit checklist. */
export const ALPHA_RECOMMENDED_DIAGNOSTICS: RecommendedDiagnostic[] = [
  { id: "ps-cbc", label: "P.S. for CBC" },
  { id: "bg", label: "BG" },
  { id: "s-bilirubin", label: "S. Bilirubin" },
  { id: "widal", label: "Widal" },
  { id: "upt", label: "UPT" },
  { id: "tsd-esr", label: "T&S D, ESR" },
  { id: "vdrl", label: "VDRL" },
  { id: "sugar-g75", label: "Sugar (G-75)" },
  { id: "b-urea", label: "B. urea" },
  { id: "hba1c", label: "HbA1c" },
  { id: "prolactin", label: "Prolactin" },
  { id: "s-creatinine", label: "S. creatinine" },
  { id: "lft", label: "LFT" },
  { id: "rft", label: "RFT" },
  { id: "mt-test", label: "MT test" },
  { id: "hiv", label: "HIV I & II" },
  { id: "hbsag", label: "HBsAg" },
  { id: "usg", label: "USG" },
  { id: "platelet", label: "Platelet count" },
  { id: "pap-smear", label: "Pap smear" },
  { id: "thyroid", label: "FT3, FT4, TSH" },
  { id: "urine-rm", label: "Urine R/M" },
  { id: "urine-as", label: "Urine A/S" },
  { id: "urine-cs", label: "Urine C/S" },
  { id: "vit-b12", label: "Vit B12" },
  { id: "vit-d", label: "Vit D" },
  { id: "amh", label: "AMH" },
  { id: "fsh", label: "FSH" },
  { id: "lh", label: "LH" },
  { id: "bt-ct", label: "BT/CT" },
  { id: "inr", label: "INR" },
];

export const INVESTIGATIONS_PREFIX = "Investigations advised:";

export function formatInvestigationsLine(labels: string[]): string {
  if (labels.length === 0) return "";
  return `${INVESTIGATIONS_PREFIX} ${labels.join(", ")}`;
}

export function stripInvestigationsLine(lines: string[]): string[] {
  return lines.filter((line) => !line.trim().startsWith(INVESTIGATIONS_PREFIX));
}
