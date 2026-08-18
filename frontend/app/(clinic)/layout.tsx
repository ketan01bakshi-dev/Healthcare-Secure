"use client";

import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import ClinicNav from "@/components/ClinicNav";
import DoctorGate from "@/components/DoctorGate";
import LockedPatientChip from "@/components/LockedPatientChip";
import { PatientProvider, usePatient } from "@/context/PatientContext";
import { I18nProvider } from "@/lib/i18n";

function ClearPatientOnSignOutBridge() {
  const { clearPatient } = usePatient();
  useEffect(() => {
    (
      window as unknown as { __healthcareClearPatient?: () => void }
    ).__healthcareClearPatient = clearPatient;
    return () => {
      delete (window as unknown as { __healthcareClearPatient?: () => void })
        .__healthcareClearPatient;
    };
  }, [clearPatient]);
  return null;
}

function ClinicShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "";
  // Patient chip not on Today (OPD ops), Patient (full PatientBar), or More
  const hideChip =
    pathname.startsWith("/today") ||
    pathname.startsWith("/patient") ||
    pathname.startsWith("/more");

  return (
    <div className="space-y-4 pb-24">
      {!hideChip ? <LockedPatientChip /> : null}
      {children}
      <ClinicNav />
    </div>
  );
}

export default function ClinicLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <PatientProvider>
        <ClearPatientOnSignOutBridge />
        <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col overflow-x-hidden bg-white px-4 pb-6 pt-[max(1.5rem,env(safe-area-inset-top))] sm:px-6 sm:pb-10 sm:pt-[max(2.5rem,env(safe-area-inset-top))]">
          <div className="w-full">
            <DoctorGate>
              <ClinicShell>{children}</ClinicShell>
            </DoctorGate>
          </div>
        </main>
      </PatientProvider>
    </I18nProvider>
  );
}
