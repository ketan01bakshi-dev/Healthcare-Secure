"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
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
  push: (n: Omit<AppNotification, "id" | "createdAt" | "read">) => void;
  markAllRead: () => void;
  clear: () => void;
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<AppNotification[]>([]);

  const push = useCallback(
    (n: Omit<AppNotification, "id" | "createdAt" | "read">) => {
      setItems((prev) => [
        {
          ...n,
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          createdAt: Date.now(),
          read: false,
        },
        ...prev,
      ].slice(0, 50));
    },
    [],
  );

  const markAllRead = useCallback(() => {
    setItems((prev) => prev.map((i) => ({ ...i, read: true })));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const unreadCount = items.filter((i) => !i.read).length;

  const value = useMemo(
    () => ({ items, unreadCount, push, markAllRead, clear }),
    [items, unreadCount, push, markAllRead, clear],
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
