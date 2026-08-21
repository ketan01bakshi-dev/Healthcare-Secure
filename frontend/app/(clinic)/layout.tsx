"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, type ReactNode } from "react";

import ClinicNav from "@/components/ClinicNav";
import DoctorGate, { useActiveClinicRole } from "@/components/DoctorGate";
import LockedPatientChip from "@/components/LockedPatientChip";
import { NotificationProvider } from "@/context/NotificationContext";
import { PatientProvider, usePatient } from "@/context/PatientContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { useSwipeTabs } from "@/hooks/useSwipeTabs";
import { lightHaptic } from "@/lib/haptics";
import { I18nProvider } from "@/lib/i18n";
import { activeHomeTabHref, homeTabHrefsForRole } from "@/lib/tabOrder";

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
  const router = useRouter();
  const role = useActiveClinicRole();
  const isHome = pathname.startsWith("/home/");
  const hideChip =
    isHome ||
    pathname.startsWith("/today") ||
    pathname.startsWith("/patient") ||
    pathname.startsWith("/more");

  // Lab desk lives outside HomeShell — still allow swipe between lab tabs
  const labTabHrefs = useMemo(
    () => (role === "lab" && !isHome ? homeTabHrefsForRole("lab") : []),
    [role, isHome],
  );
  const labActive = useMemo(
    () => activeHomeTabHref(pathname, labTabHrefs),
    [pathname, labTabHrefs],
  );
  const onLabSwipe = useCallback(
    (next: string) => {
      if (next === labActive) return;
      lightHaptic();
      router.push(next);
    },
    [labActive, router],
  );
  const labSwipe = useSwipeTabs({
    items: labTabHrefs,
    active: labActive,
    onChange: onLabSwipe,
  });

  if (isHome) {
    return <div className="space-y-4">{children}</div>;
  }

  return (
    <div className="space-y-4 pb-24" {...(labTabHrefs.length ? labSwipe : {})}>
      {!hideChip ? <LockedPatientChip /> : null}
      {children}
      <ClinicNav />
    </div>
  );
}

export default function ClinicLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <ThemeProvider>
        <NotificationProvider>
          <PatientProvider>
            <ClearPatientOnSignOutBridge />
            <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col overflow-x-hidden bg-white px-4 pb-6 pt-[max(1.5rem,env(safe-area-inset-top))] dark:bg-slate-950 sm:px-6 sm:pb-10 sm:pt-[max(2.5rem,env(safe-area-inset-top))]">
              <div className="w-full">
                <DoctorGate>
                  <ClinicShell>{children}</ClinicShell>
                </DoctorGate>
              </div>
            </main>
          </PatientProvider>
        </NotificationProvider>
      </ThemeProvider>
    </I18nProvider>
  );
}
