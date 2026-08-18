"use client";

import { lightHaptic } from "@/lib/haptics";

type Props = {
  onClick: () => void;
  className?: string;
};

export default function FabButton({ onClick, className = "" }: Props) {
  return (
    <button
      aria-label="Create"
      className={`fixed right-4 z-20 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-2xl font-light text-white shadow-lg active:scale-95 dark:bg-teal-600 ${className}`}
      onClick={() => {
        lightHaptic();
        onClick();
      }}
      type="button"
    >
      +
    </button>
  );
}
