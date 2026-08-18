"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import CollapsibleSection from "@/components/CollapsibleSection";
import { usePatient } from "@/context/PatientContext";
import { apiFetch } from "@/lib/doctorSession";
import { useI18n } from "@/lib/i18n";

type BillingSummary = {
  currency: string;
  today_charges_inr: number;
  total_charges_inr: number;
  total_paid_inr: number;
  amount_due_inr: number;
};

type QrPayment = {
  payment_id: string;
  amount_inr: number;
  status: string;
  qr_string: string;
  qr_image_base64: string;
  qr_image_url: string;
  expires_at: string | null;
};

function formatInr(n: number): string {
  return `₹${n.toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

/** Per-patient billing ledger: today's charges, paid to date, amount due. */
export default function PatientBilling() {
  const { t } = useI18n();
  const { locked, rawIdentifier, bumpHistory, historyVersion } = usePatient();
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [paymentsEnabled, setPaymentsEnabled] = useState(false);
  const [qr, setQr] = useState<QrPayment | null>(null);
  const [qrStatus, setQrStatus] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadSummary = useCallback(async () => {
    if (!locked || !rawIdentifier) {
      setSummary(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/history/billing-summary", {
        method: "POST",
        body: JSON.stringify({ raw_identifier: rawIdentifier }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSummary((await res.json()) as BillingSummary);
    } catch (e) {
      setSummary(null);
      setError(e instanceof Error ? e.message : t("billingLoadFailed"));
    } finally {
      setLoading(false);
    }
  }, [locked, rawIdentifier, t]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary, historyVersion]);

  useEffect(() => {
    if (!locked) {
      setPaymentsEnabled(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch("/api/v1/payments/status");
        if (!res.ok || cancelled) return;
        const body = (await res.json()) as { payments_enabled?: boolean };
        if (!cancelled) setPaymentsEnabled(Boolean(body.payments_enabled));
      } catch {
        if (!cancelled) setPaymentsEnabled(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locked]);

  useEffect(() => () => stopPoll(), [stopPoll]);

  const submit = async (kind: "charge" | "payment") => {
    if (!locked || !rawIdentifier) return;
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) {
      setError(t("billAmountInvalid"));
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch("/api/v1/history/billing", {
        method: "POST",
        body: JSON.stringify({
          raw_identifier: rawIdentifier,
          amount_inr: value,
          note: note.trim(),
          kind,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setAmount("");
      setNote("");
      setNotice(kind === "payment" ? t("paymentRecorded") : t("chargeRecorded"));
      bumpHistory();
      await loadSummary();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("billSaveFailed"));
    } finally {
      setBusy(false);
    }
  };

  const closeQr = useCallback(() => {
    stopPoll();
    setQr(null);
    setQrStatus(null);
  }, [stopPoll]);

  const startPoll = useCallback(
    (paymentId: string) => {
      stopPoll();
      pollRef.current = setInterval(() => {
        void (async () => {
          try {
            const res = await apiFetch(`/api/v1/payments/${paymentId}`);
            if (!res.ok) return;
            const body = (await res.json()) as {
              status: string;
            };
            setQrStatus(body.status);
            if (body.status === "paid") {
              stopPoll();
              setNotice(t("qrPaymentPaid"));
              bumpHistory();
              await loadSummary();
              setTimeout(() => closeQr(), 1200);
            } else if (body.status === "expired" || body.status === "failed") {
              stopPoll();
            }
          } catch {
            /* keep polling */
          }
        })();
      }, 2500);
    },
    [bumpHistory, closeQr, loadSummary, stopPoll, t],
  );

  const showPayQr = async () => {
    if (!locked || !rawIdentifier) return;
    const typed = Number(amount);
    const due = summary?.amount_due_inr ?? 0;
    const hasTyped = Number.isFinite(typed) && typed > 0;
    if (!hasTyped && due <= 0) {
      setError(t("billAmountInvalid"));
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const payload: { raw_identifier: string; amount_inr?: number } = {
        raw_identifier: rawIdentifier,
      };
      if (hasTyped) payload.amount_inr = typed;
      const res = await apiFetch("/api/v1/payments/qr", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (res.status === 503) {
        setError(t("paymentsUnavailable"));
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const body = (await res.json()) as QrPayment;
      setQr(body);
      setQrStatus(body.status);
      startPoll(body.payment_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("qrCreateFailed"));
    } finally {
      setBusy(false);
    }
  };

  if (!locked) return null;

  const canShowQr =
    paymentsEnabled &&
    ((Number(amount) > 0 && Number.isFinite(Number(amount))) ||
      (summary?.amount_due_inr ?? 0) > 0);

  return (
    <CollapsibleSection hint={t("billingHint")} title={t("billingSection")}>
      {loading && !summary ? (
        <p className="text-sm text-slate-500">{t("loadingSummary")}</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Stat label={t("todayCharges")} value={formatInr(summary?.today_charges_inr ?? 0)} />
          <Stat label={t("totalPaidTillDate")} value={formatInr(summary?.total_paid_inr ?? 0)} />
          <Stat label={t("amountDue")} value={formatInr(summary?.amount_due_inr ?? 0)} emphasis />
        </div>
      )}

      <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="block flex-1 text-xs text-slate-600">
            {t("billAmountInr")}
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
              disabled={busy}
              inputMode="decimal"
              min="0"
              onChange={(e) => setAmount(e.target.value)}
              placeholder="500"
              step="0.01"
              type="number"
              value={amount}
            />
          </label>
          <label className="block flex-[1.4] text-xs text-slate-600">
            {t("billNote")}
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
              disabled={busy}
              maxLength={200}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("billNotePlaceholder")}
              type="text"
              value={note}
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-medium text-white disabled:opacity-50"
            disabled={busy}
            onClick={() => void submit("charge")}
            type="button"
          >
            {busy ? t("saving") : t("addCharge")}
          </button>
          <button
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 disabled:opacity-50"
            disabled={busy}
            onClick={() => void submit("payment")}
            type="button"
          >
            {busy ? t("saving") : t("recordPayment")}
          </button>
          {paymentsEnabled ? (
            <button
              className="min-h-11 rounded-lg border border-emerald-600 bg-emerald-50 px-4 text-sm font-medium text-emerald-900 disabled:opacity-50"
              disabled={busy || !canShowQr}
              onClick={() => void showPayQr()}
              type="button"
            >
              {busy ? t("saving") : t("showPayQr")}
            </button>
          ) : (
            <p className="self-center text-xs text-slate-500">{t("paymentsUnavailable")}</p>
          )}
        </div>
      </div>

      {qr ? (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 text-center">
          <p className="text-sm font-medium text-slate-900">
            {t("scanToPay")} · {formatInr(qr.amount_inr)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {qrStatus === "paid"
              ? t("qrPaymentPaid")
              : qrStatus === "expired"
                ? t("qrPaymentExpired")
                : t("waitingForPayment")}
          </p>
          {qr.qr_image_base64 ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              alt="UPI QR"
              className="mx-auto mt-3 h-56 w-56 rounded-lg border border-slate-100 bg-white object-contain p-2"
              src={`data:image/png;base64,${qr.qr_image_base64}`}
            />
          ) : qr.qr_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              alt="UPI QR"
              className="mx-auto mt-3 h-56 w-56 rounded-lg border border-slate-100 bg-white object-contain p-2"
              src={qr.qr_image_url}
            />
          ) : (
            <p className="mt-3 break-all text-xs text-slate-600">{qr.qr_string}</p>
          )}
          <button
            className="mt-3 min-h-11 rounded-lg border border-slate-300 px-4 text-sm text-slate-700"
            onClick={closeQr}
            type="button"
          >
            {t("closeQr")}
          </button>
        </div>
      ) : null}

      {notice ? <p className="mt-2 text-sm text-emerald-700">{notice}</p> : null}
      {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
    </CollapsibleSection>
  );
}

function Stat({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={
        emphasis
          ? "rounded-lg border border-amber-200 bg-amber-50 px-3 py-2"
          : "rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
      }
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p
        className={
          emphasis
            ? "mt-1 text-lg font-semibold text-amber-950"
            : "mt-1 text-lg font-semibold text-slate-900"
        }
      >
        {value}
      </p>
    </div>
  );
}
