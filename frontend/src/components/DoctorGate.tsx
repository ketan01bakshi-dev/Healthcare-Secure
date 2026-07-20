"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";

import {
  type ClinicUserInfo,
  fetchAuthStatus,
  getClinicUser,
  getDoctorSession,
  lockDoctorSession,
  unlockClinicUser,
} from "@/lib/doctorSession";

type Props = {
  children: ReactNode;
};

export default function DoctorGate({ children }: Props) {
  const [checking, setChecking] = useState(true);
  const [authRequired, setAuthRequired] = useState(false);
  const [users, setUsers] = useState<ClinicUserInfo[]>([]);
  const [unlocked, setUnlocked] = useState(false);
  const [userId, setUserId] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeUser, setActiveUser] = useState<ClinicUserInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await fetchAuthStatus();
        if (cancelled) return;
        setAuthRequired(status.auth_required);
        setUsers(status.users);
        if (status.users[0]) setUserId(status.users[0].user_id);
        if (!status.auth_required) {
          setUnlocked(true);
          setActiveUser({
            user_id: "local",
            display_name: "Local doctor",
            role: "doctor",
          });
        } else {
          const existing = getClinicUser();
          const hasSession = !!getDoctorSession();
          setUnlocked(hasSession && !!existing);
          setActiveUser(hasSession ? existing : null);
        }
      } catch {
        if (!cancelled) {
          setAuthRequired(false);
          setUnlocked(true);
          setActiveUser({
            user_id: "local",
            display_name: "Local doctor",
            role: "doctor",
          });
        }
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onUnlock = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        const user = await unlockClinicUser(userId, pin);
        setActiveUser(user);
        setUnlocked(true);
        setPin("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unlock failed");
      } finally {
        setBusy(false);
      }
    },
    [pin, userId],
  );

  const onLock = useCallback(async () => {
    await lockDoctorSession();
    setUnlocked(false);
    setActiveUser(null);
  }, []);

  if (checking) {
    return (
      <p className="mx-auto max-w-3xl px-4 py-10 text-sm text-slate-500">
        Checking clinic lock…
      </p>
    );
  }

  if (authRequired && !unlocked) {
    return (
      <section className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white px-4 py-8 shadow-sm sm:px-6">
        <h2 className="text-lg font-semibold text-slate-900">
          Clinic sign-in
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Select your name and enter your PIN to continue.
        </p>
        <form className="mt-5 flex flex-col gap-3" onSubmit={onUnlock}>
          <label className="text-xs uppercase tracking-wide text-slate-500">
            Your name
            <select
              aria-label="Clinic user"
              className="mt-1 min-h-12 w-full rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900"
              onChange={(e) => setUserId(e.target.value)}
              value={userId}
            >
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.display_name}
                  {u.role === "doctor" ? " — Doctor" : " — Staff"}
                </option>
              ))}
            </select>
          </label>
          <input
            aria-label="Clinic PIN"
            autoComplete="current-password"
            className="min-h-12 rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none ring-clinical-500 focus:ring-2"
            inputMode="numeric"
            onChange={(e) => setPin(e.target.value)}
            placeholder="Your PIN"
            type="password"
            value={pin}
          />
          <button
            className="inline-flex min-h-12 items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60"
            disabled={busy || !pin.trim() || !userId}
            type="submit"
          >
            {busy ? "Please wait…" : "Sign in"}
          </button>
        </form>
        {error ? (
          <p className="mt-3 text-sm text-red-600" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-1">
        <p className="text-xs text-slate-500">
          {activeUser
            ? `Signed in as ${activeUser.display_name}`
            : "Signed in"}
        </p>
        {authRequired ? (
          <button
            className="min-h-10 rounded-lg border border-slate-200 px-3 text-xs text-slate-700"
            onClick={() => void onLock()}
            type="button"
          >
            Sign out
          </button>
        ) : null}
      </div>
      <ClinicUserBridge user={activeUser}>{children}</ClinicUserBridge>
    </div>
  );
}

function ClinicUserBridge({
  user,
  children,
}: {
  user: ClinicUserInfo | null;
  children: ReactNode;
}) {
  useEffect(() => {
    (
      window as unknown as { __healthcareClinicUser?: ClinicUserInfo | null }
    ).__healthcareClinicUser = user;
    (
      window as unknown as { __healthcareDoctorName?: string }
    ).__healthcareDoctorName = user?.display_name || "";
  }, [user]);
  return <>{children}</>;
}

export function getPrefillDoctorName(): string {
  if (typeof window === "undefined") return "";
  return (
    (window as unknown as { __healthcareDoctorName?: string })
      .__healthcareDoctorName || ""
  );
}

export function useActiveClinicRole(): ClinicRoleOrLocal {
  const [role, setRole] = useState<ClinicRoleOrLocal>(() =>
    getClinicUser()?.role === "staff" ? "staff" : "doctor",
  );
  useEffect(() => {
    const user = getClinicUser();
    setRole(user?.role === "staff" ? "staff" : "doctor");
  }, []);
  return role;
}

type ClinicRoleOrLocal = "doctor" | "staff";
