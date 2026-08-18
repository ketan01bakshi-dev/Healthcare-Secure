"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useClinicFeatures, useActiveClinicRole } from "@/components/DoctorGate";
import NeedPatient from "@/components/NeedPatient";
import PatientBar from "@/components/PatientBar";
import ObstetricProfileForm from "@/components/ObstetricProfileForm";
import OngoingHealthForm from "@/components/OngoingHealthForm";
import VitalsForm from "@/components/VitalsForm";
import { usePatient } from "@/context/PatientContext";
import { useI18n } from "@/lib/i18n";

export default function PatientPage() {
  const role = useActiveClinicRole();
  const { has } = useClinicFeatures();
  const { locked } = usePatient();
  const router = useRouter();
  const { t } = useI18n();

  useEffect(() => {
    if (role === "receptionist") {
      router.replace("/today/");
      return;
    }
    if (role === "lab") {
      router.replace(locked ? "/labs/" : "/today/");
    }
  }, [role, router, locked]);

  if (role === "receptionist" || role === "lab") {
    return (
      <p className="text-sm text-slate-500">
        {role === "lab" ? t("redirectingToLabs") : t("redirectingToToday")}
      </p>
    );
  }

  return (
    <NeedPatient>
      <div className="space-y-6">
        <PatientBar />
        <VitalsForm />
        {has("obstetric") ? <ObstetricProfileForm /> : null}
        <OngoingHealthForm />
      </div>
    </NeedPatient>
  );
}
