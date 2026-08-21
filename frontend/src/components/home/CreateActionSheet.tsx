"use client";

import { useRouter } from "next/navigation";

import OverlayBackdrop from "@/components/overlays/OverlayBackdrop";
import { useI18n } from "@/lib/i18n";
import { lightHaptic } from "@/lib/haptics";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function CreateActionSheet({ open, onClose }: Props) {
  const { t } = useI18n();
  const router = useRouter();

  if (!open) return null;

  function go(path: string) {
    lightHaptic();
    onClose();
    router.push(path);
  }

  return (
    <>
      <OverlayBackdrop onDismiss={onClose} />
      <div className="fixed bottom-28 left-1/2 z-50 w-[min(20rem,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl dark:border-slate-600 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-center gap-2">
          <button
            className="rounded-full bg-teal-600 px-5 py-2.5 text-sm font-medium text-white"
            onClick={() => go("/home/calendar/new/")}
            type="button"
          >
            {t("createAppointment")}
          </button>
          <button
            className="rounded-full bg-slate-800 px-5 py-2.5 text-sm font-medium text-white dark:bg-slate-200 dark:text-slate-900"
            onClick={() => go("/home/patients/new/")}
            type="button"
          >
            {t("createPatient")}
          </button>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            aria-label={t("cancel")}
            className="min-h-10 min-w-10 rounded-full text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            onClick={onClose}
            type="button"
          >
            ✕
          </button>
        </div>
      </div>
    </>
  );
}
