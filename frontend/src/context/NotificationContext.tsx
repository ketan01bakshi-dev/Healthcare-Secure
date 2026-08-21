"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type AppNotification = {
  id: string;
  title: string;
  body: string;
  href?: string;
  createdAt: number;
  read: boolean;
};

type NotificationContextValue = {
  items: AppNotification[];
  unreadCount: number;
  /** Latest toast currently shown (null when hidden). */
  toast: AppNotification | null;
  push: (n: Omit<AppNotification, "id" | "createdAt" | "read">) => void;
  dismissToast: () => void;
  markAllRead: () => void;
  clear: () => void;
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

const TOAST_MS = 3200;

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [toast, setToast] = useState<AppNotification | null>(null);
  const toastTimer = useRef<number | null>(null);

  const dismissToast = useCallback(() => {
    if (toastTimer.current != null) {
      window.clearTimeout(toastTimer.current);
      toastTimer.current = null;
    }
    setToast(null);
  }, []);

  const push = useCallback(
    (n: Omit<AppNotification, "id" | "createdAt" | "read">) => {
      const item: AppNotification = {
        ...n,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        createdAt: Date.now(),
        read: false,
      };
      setItems((prev) => [item, ...prev].slice(0, 50));
      setToast(item);
      if (toastTimer.current != null) {
        window.clearTimeout(toastTimer.current);
      }
      toastTimer.current = window.setTimeout(() => {
        setToast(null);
        toastTimer.current = null;
      }, TOAST_MS);
    },
    [],
  );

  useEffect(() => {
    return () => {
      if (toastTimer.current != null) {
        window.clearTimeout(toastTimer.current);
      }
    };
  }, []);

  const markAllRead = useCallback(() => {
    setItems((prev) => prev.map((i) => ({ ...i, read: true })));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const unreadCount = items.filter((i) => !i.read).length;

  const value = useMemo(
    () => ({
      items,
      unreadCount,
      toast,
      push,
      dismissToast,
      markAllRead,
      clear,
    }),
    [items, unreadCount, toast, push, dismissToast, markAllRead, clear],
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications(): NotificationContextValue {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error("useNotifications must be used within NotificationProvider");
  }
  return ctx;
}
