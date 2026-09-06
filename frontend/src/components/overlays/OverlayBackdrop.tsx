"use client";

type Props = {
  onDismiss: () => void;
  className?: string;
};

/** Tap empty space to close overlays — blurs and dims the screen behind. */
export default function OverlayBackdrop({ onDismiss, className = "" }: Props) {
  return (
    <button
      aria-label="Close"
      className={`fixed inset-0 z-40 bg-slate-900/55 backdrop-blur-md ${className}`}
      onClick={onDismiss}
      type="button"
    />
  );
}
