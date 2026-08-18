"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { usePatient } from "@/context/PatientContext";
import { useI18n } from "@/lib/i18n";

/** Blocks clinical pages until a patient is locked. */
export default function NeedPatient({ children }: { children: ReactNode }) {
  const { locked } = usePatient();
  const { t } = useI18n();

  if (!locked) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-6 text-center">
        <p className="text-sm font-medium text-amber-950">
          {t("selectPatientFirst")}
        </p>
        <p className="mt-2 text-sm text-amber-900/80">{t("selectPatientFirstHint")}</p>
        <Link
          href="/today/#all-patients"
          className="mt-4 inline-flex min-h-12 items-center justify-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white"
        >
          {t("selectPatient")}
        </Link>
      </section>
    );
  }

  return <>{children}</>;
}
