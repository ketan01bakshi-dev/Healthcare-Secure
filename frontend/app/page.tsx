"use client";

import DocumentUpload from "@/components/DocumentUpload";
import DoctorGate, { useActiveClinicRole } from "@/components/DoctorGate";
import EncounterWorkspace from "@/components/EncounterWorkspace";
import PatientAttachments from "@/components/PatientAttachments";
import PatientBar from "@/components/PatientBar";
import PatientTimeline from "@/components/PatientTimeline";
import VitalsForm from "@/components/VitalsForm";
import { PatientProvider } from "@/context/PatientContext";

function DashboardBody() {
  const role = useActiveClinicRole();
  const isDoctor = role === "doctor";

  return (
    <>
      <PatientBar />
      <VitalsForm />
      {isDoctor ? <EncounterWorkspace /> : (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          You are signed in as staff. You can add vitals, notes, and reports.
          Ask a doctor to write and sign the prescription.
        </p>
      )}
      <DocumentUpload />
      <PatientTimeline />
      <PatientAttachments />
    </>
  );
}

export default function HomePage() {
  return (
    <PatientProvider>
      <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col overflow-x-hidden bg-white px-4 py-6 sm:px-6 sm:py-8">
        <div className="w-full space-y-8 sm:space-y-10">
          <DoctorGate>
            <DashboardBody />
          </DoctorGate>
        </div>
      </main>
    </PatientProvider>
  );
}
