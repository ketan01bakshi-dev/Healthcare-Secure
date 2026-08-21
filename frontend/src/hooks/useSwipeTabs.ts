"use client";

import { useCallback, useRef, type TouchEvent } from "react";

type Options = {
  /** Ordered list of destinations (hrefs or tab keys). */
  items: string[];
  /** Current active item. */
  active: string;
  /** Called with the next/previous item on a successful swipe. */
  onChange: (next: string) => void;
  /** Minimum horizontal travel in px (default 56). */
  threshold?: number;
  /** Ignore swipe if vertical travel is larger than this ratio of horizontal. */
  verticalGuard?: number;
};

/**
 * Horizontal swipe between ordered tabs.
 * Returns touch handlers to spread onto a content container.
 */
export function useSwipeTabs({
  items,
  active,
  onChange,
  threshold = 56,
  verticalGuard = 1.2,
}: Options) {
  const startX = useRef(0);
  const startY = useRef(0);
  const tracking = useRef(false);

  const onTouchStart = useCallback((e: TouchEvent) => {
    if (e.touches.length !== 1) return;
    startX.current = e.touches[0].clientX;
    startY.current = e.touches[0].clientY;
    tracking.current = true;
  }, []);

  const onTouchEnd = useCallback(
    (e: TouchEvent) => {
      if (!tracking.current || items.length < 2) return;
      tracking.current = false;
      const touch = e.changedTouches[0];
      if (!touch) return;
      const dx = touch.clientX - startX.current;
      const dy = touch.clientY - startY.current;
      if (Math.abs(dx) < threshold) return;
      if (Math.abs(dy) > Math.abs(dx) * verticalGuard) return;

      const idx = items.indexOf(active);
      if (idx < 0) return;

      // Swipe left → next; swipe right → previous
      if (dx < 0 && idx < items.length - 1) {
        onChange(items[idx + 1]);
      } else if (dx > 0 && idx > 0) {
        onChange(items[idx - 1]);
      }
    },
    [active, items, onChange, threshold, verticalGuard],
  );

  const onTouchCancel = useCallback(() => {
    tracking.current = false;
  }, []);

  return { onTouchStart, onTouchEnd, onTouchCancel };
}
