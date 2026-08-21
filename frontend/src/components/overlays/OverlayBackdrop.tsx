"use client";

type Props = {
  onDismiss: () => void;
  className?: string;
};

/** Tap empty space to close overlays — no navigation. */
export default function OverlayBackdrop({ onDismiss, className = "" }: Props) {
  return (
    <button
      aria-label="Close"
      className={`fixed inset-0 z-40 bg-black/30 ${className}`}
      onClick={onDismiss}
      type="button"
    />
  );
}
