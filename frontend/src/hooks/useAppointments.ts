"use client";

import { useCallback, useEffect, useState } from "react";

import type { AppointmentRow } from "@/lib/appointmentGroups";
import { apiFetch } from "@/lib/doctorSession";

function notifyChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("healthcare-appointments-changed"));
  }
}

export function useAppointments(opts?: {
  from?: string;
  to?: string;
  status?: string;
}) {
  const [items, setItems] = useState<AppointmentRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (opts?.status) params.set("status", opts.status);
      if (opts?.from) params.set("from_date", opts.from);
      if (opts?.to) params.set("to_date", opts.to);
      const qs = params.toString();
      const res = await apiFetch(
        `/api/v1/appointments${qs ? `?${qs}` : ""}`,
      );
      if (!res.ok) return;
      const data = (await res.json()) as AppointmentRow[];
      setItems(Array.isArray(data) ? data : []);
    } catch {
      /* offline */
    } finally {
      setLoading(false);
    }
  }, [opts?.from, opts?.status, opts?.to]);

  useEffect(() => {
    void load();
    const onChange = () => void load();
    window.addEventListener("healthcare-appointments-changed", onChange);
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, 30000);
    return () => {
      window.removeEventListener("healthcare-appointments-changed", onChange);
      window.clearInterval(id);
    };
  }, [load]);

  return { items, loading, reload: load };
}

export { notifyChanged as notifyAppointmentsChanged };
