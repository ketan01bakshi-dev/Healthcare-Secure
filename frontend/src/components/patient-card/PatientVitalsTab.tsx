"use client";

import { useClinicFeatures } from "@/components/DoctorGate";
import ObstetricProfileForm from "@/components/ObstetricProfileForm";
import OngoingHealthForm from "@/components/OngoingHealthForm";
import PatientBar from "@/components/PatientBar";
import VitalsForm from "@/components/VitalsForm";

export default function PatientVitalsTab() {
  const { has } = useClinicFeatures();
  return (
    <div className="space-y-6 pt-4">
      <PatientBar />
      <VitalsForm />
      {has("obstetric") ? <ObstetricProfileForm /> : null}
      <OngoingHealthForm />
    </div>
  );
}
