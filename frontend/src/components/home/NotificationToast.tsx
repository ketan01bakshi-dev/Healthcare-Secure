"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useNotifications } from "@/context/NotificationContext";
import { lightHaptic } from "@/lib/haptics";

type Props = {
  className?: string;
};

/** Brief toast after booking — not a permanent bubble. */
export default function NotificationToast({ className = "" }: Props) {
  const { toast, dismissToast } = useNotifications();
  const router = useRouter();

  useEffect(() => {
    if (toast) lightHaptic();
  }, [toast]);

  if (!toast) return null;

  return (
    <button
      className={`fixed left-1/2 z-40 w-[min(22rem,calc(100vw-2rem))] -translate-x-1/2 animate-[fadeSlideUp_0.25s_ease-out] rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-left shadow-lg dark:border-emerald-800 dark:bg-emerald-950 ${className}`}
      onClick={() => {
        dismissToast();
        if (toast.href) router.push(toast.href);
      }}
      type="button"
    >
      <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-100">
        {toast.title}
      </p>
      {toast.body ? (
        <p className="mt-0.5 text-xs text-emerald-800/80 dark:text-emerald-200/80">
          {toast.body}
        </p>
      ) : null}
    </button>
  );
}
