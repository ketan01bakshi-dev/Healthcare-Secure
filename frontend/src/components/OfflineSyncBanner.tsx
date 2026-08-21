"use client";

import { useEffect, useState } from "react";

import { flushOfflineQueue, pendingOfflineCount } from "@/lib/offlineQueue";
import { useI18n } from "@/lib/i18n";

export default function OfflineSyncBanner() {
  const { t } = useI18n();
  const [pending, setPending] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const tick = () => setPending(pendingOfflineCount());
    tick();
    void flushOfflineQueue().then((r) => {
      if (r.dropped) {
        setMsg(`Removed ${r.dropped} invalid offline save(s).`);
      } else if (r.sent) {
        setMsg(`Synced ${r.sent} offline save(s).`);
      }
      tick();
    });
    const id = window.setInterval(tick, 5000);
    const onOnline = () => {
      void flushOfflineQueue().then((r) => {
        if (r.sent) setMsg(`Synced ${r.sent} offline save(s).`);
        if (r.dropped) setMsg(`Removed ${r.dropped} invalid offline save(s).`);
        tick();
      });
    };
    window.addEventListener("online", onOnline);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("online", onOnline);
    };
  }, []);

  if (!pending && !msg) return null;
  return (
    <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      {pending ? `${pending} ${t("offlinePending")} ` : null}
      {msg}
      {pending ? (
        <button
          className="ml-2 underline"
          onClick={() =>
            void flushOfflineQueue().then((r) => {
              if (r.sent) setMsg(`Synced ${r.sent}.`);
              else if (r.dropped)
                setMsg(`Removed ${r.dropped} invalid save(s).`);
              else setMsg("Nothing to sync.");
              setPending(r.remaining);
            })
          }
          type="button"
        >
          {t("syncNow")}
        </button>
      ) : null}
    </p>
  );
}
