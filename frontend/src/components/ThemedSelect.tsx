"use client";

import { useId, useState } from "react";

import OverlayBackdrop from "@/components/overlays/OverlayBackdrop";
import { useI18n } from "@/lib/i18n";

export type ThemedSelectOption = {
  value: string;
  label: string;
};

type Props = {
  value: string;
  options: ThemedSelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Accessible name for the trigger / dialog. */
  "aria-label"?: string;
  className?: string;
  id?: string;
};

/**
 * App-themed single-select (replaces native OS pickers that ignore light UI).
 */
export default function ThemedSelect({
  value,
  options,
  onChange,
  disabled = false,
  "aria-label": ariaLabel,
  className = "",
  id,
}: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const autoId = useId();
  const listId = id || autoId;
  const selected =
    options.find((o) => o.value === value) ?? options[0] ?? { value: "", label: "—" };

  return (
    <>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={ariaLabel}
        className={`mt-1 flex min-h-11 w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 text-left text-sm text-slate-900 outline-none ring-slate-400 focus:ring-2 disabled:opacity-60 ${className}`}
        disabled={disabled}
        id={listId}
        onClick={() => setOpen(true)}
        type="button"
      >
        <span className="truncate">{selected.label}</span>
        <span aria-hidden className="text-slate-400">
          ▾
        </span>
      </button>

      {open ? (
        <>
          <OverlayBackdrop onDismiss={() => setOpen(false)} />
          <div
            aria-labelledby={listId}
            className="fixed left-1/2 top-1/2 z-50 w-[min(20rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-600 dark:bg-slate-900"
            role="dialog"
          >
            <ul className="max-h-[min(22rem,70vh)] overflow-y-auto py-1" role="listbox">
              {options.map((opt) => {
                const active = opt.value === value;
                return (
                  <li key={opt.value || "__empty"}>
                    <button
                      aria-selected={active}
                      className={`flex min-h-12 w-full items-center justify-between gap-3 border-b border-slate-100 px-4 text-left text-sm last:border-b-0 dark:border-slate-700 ${
                        active
                          ? "bg-clinical-50 font-medium text-clinical-900 dark:bg-clinical-900/40 dark:text-clinical-50"
                          : "bg-white text-slate-900 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                      }`}
                      onClick={() => {
                        onChange(opt.value);
                        setOpen(false);
                      }}
                      role="option"
                      type="button"
                    >
                      <span>{opt.label}</span>
                      <span
                        aria-hidden
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
                          active
                            ? "border-clinical-500 bg-clinical-500"
                            : "border-slate-300 bg-white dark:border-slate-500 dark:bg-slate-900"
                        }`}
                      >
                        {active ? (
                          <span className="h-2 w-2 rounded-full bg-white" />
                        ) : null}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="border-t border-slate-100 px-3 py-2 dark:border-slate-700">
              <button
                className="min-h-10 w-full rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                onClick={() => setOpen(false)}
                type="button"
              >
                {t("cancel")}
              </button>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
