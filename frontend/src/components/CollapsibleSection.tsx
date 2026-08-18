"use client";

import { ReactNode, useId, useState } from "react";

type Variant = "light" | "dark";

type Props = {
  title: ReactNode;
  children: ReactNode;
  variant?: Variant;
  hint?: ReactNode;
  defaultOpen?: boolean;
  headerActions?: ReactNode;
  /** Overrides the default open-state shell classes for this variant. */
  className?: string;
  "aria-label"?: string;
};

const SHELL_OPEN: Record<Variant, string> = {
  light: "rounded-xl border border-slate-200 bg-white px-4 py-4",
  dark: "mx-auto w-full max-w-md overflow-x-hidden rounded-2xl border border-clinical-100/15 bg-clinical-900/40 px-4 py-6 sm:px-6",
};

/** Collapsed headers share one grey look on every tab. */
const SHELL_COLLAPSED =
  "rounded-xl border border-slate-200 bg-slate-100 px-4 py-4";

const TITLE: Record<Variant, string> = {
  light: "text-sm font-semibold uppercase tracking-wide text-slate-500",
  dark: "text-sm font-semibold uppercase tracking-wide text-clinical-100/70",
};

const TITLE_COLLAPSED =
  "text-sm font-semibold uppercase tracking-wide text-slate-500";

const HINT: Record<Variant, string> = {
  light: "text-sm text-slate-600",
  dark: "text-sm text-clinical-100/70",
};

const CHEVRON: Record<Variant, string> = {
  light: "text-slate-500",
  dark: "text-clinical-100/70",
};

const CHEVRON_COLLAPSED = "text-slate-500";

export default function CollapsibleSection({
  title,
  children,
  variant = "light",
  hint,
  defaultOpen = false,
  headerActions,
  className,
  "aria-label": ariaLabel,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();

  const shell = open
    ? `${className ?? SHELL_OPEN[variant]} transition-colors duration-200`
    : `${SHELL_COLLAPSED} transition-colors duration-200`;

  return (
    <section aria-label={ariaLabel} className={shell}>
      <div className="flex items-start gap-2">
        <button
          aria-controls={panelId}
          aria-expanded={open}
          className="flex min-h-11 min-w-0 flex-1 items-center gap-2 text-left"
          onClick={() => setOpen((v) => !v)}
          type="button"
        >
          <span
            className={`min-w-0 flex-1 ${open ? TITLE[variant] : TITLE_COLLAPSED}`}
          >
            {title}
          </span>
          <svg
            aria-hidden="true"
            className={`h-5 w-5 shrink-0 transition-transform ${
              open ? CHEVRON[variant] : CHEVRON_COLLAPSED
            } ${open ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            viewBox="0 0 24 24"
          >
            <path
              d="m6 9 6 6 6-6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        {headerActions ? (
          <div className="flex shrink-0 items-center gap-2 pt-0.5">
            {headerActions}
          </div>
        ) : null}
      </div>
      {open ? (
        <div className="mt-3 space-y-3" id={panelId}>
          {hint ? <div className={HINT[variant]}>{hint}</div> : null}
          {children}
        </div>
      ) : null}
    </section>
  );
}
