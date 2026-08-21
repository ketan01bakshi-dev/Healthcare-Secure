"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

import {
  type ClinicFeature,
  type ClinicGate,
  type ClinicRole,
  type ClinicUserInfo,
  ALL_CLINIC_FEATURES,
  fetchAuthMe,
  fetchAuthStatus,
  getClinicGate,
  getClinicUser,
  getDoctorSession,
  lockDoctorSession,
  previewClinicPasswordDoctors,
  recoverClinicPassword,
  resetClinicPassword,
  setClinicGate,
  switchClinic,
  unlockClinic,
  unlockClinicUser,
} from "@/lib/doctorSession";
import {
  getApiBaseUrl,
  getDefaultApiBaseUrl,
  isLoopbackApiBaseUrl,
  isNativeApp,
  needsClinicUrlSetup,
  setApiBaseUrl,
  isProductionApiLocked,
} from "@/lib/apiBase";
import { HOME_LANDING } from "@/lib/clinicRoutes";
import { useI18n } from "@/lib/i18n";

type Props = {
  children: ReactNode;
};

type ForgotStep = "clinic" | "doctor" | "password" | null;

function roleLabel(role: ClinicRole): string {
  if (role === "doctor") return "Doctor";
  if (role === "lab") return "Lab Desk";
  if (role === "receptionist") return "Front Desk";
  return "Staff";
}

function roleHint(role: ClinicRole): string {
  if (role === "doctor") return "All tabs · write and sign prescriptions";
  if (role === "lab") return "Upload lab reports only";
  if (role === "receptionist") return "Patient Info and More";
  return "Patient Info, Vitals, Records, and More";
}

/** Sign-in profile order: Front Desk → Staff → Doctor → Lab Desk */
const SIGN_IN_ROLE_ORDER: Record<ClinicRole, number> = {
  receptionist: 0,
  staff: 1,
  doctor: 2,
  lab: 3,
};

function sortUsersForSignIn(users: ClinicUserInfo[]): ClinicUserInfo[] {
  return [...users].sort((a, b) => {
    const ra = SIGN_IN_ROLE_ORDER[a.role] ?? 99;
    const rb = SIGN_IN_ROLE_ORDER[b.role] ?? 99;
    if (ra !== rb) return ra - rb;
    return (a.display_name || "").localeCompare(b.display_name || "");
  });
}

function BrandLogoTile() {
  return (
    <div className="flex min-h-36 flex-col items-center justify-center gap-3 rounded-2xl border border-slate-300 bg-slate-200/40 px-6 py-7 text-center shadow-sm">
      <img
        alt=""
        className="h-16 w-16 object-contain sm:h-20 sm:w-20"
        height={80}
        src="/aarogya-one-connect-logo.png"
        width={80}
      />
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
        Aarogya One Connect
      </h1>
    </div>
  );
}

function AlphaClinicLogoCorner() {
  return (
    <img
      alt="Alpha Clinic"
      className="pointer-events-none absolute right-1 top-4 z-10 h-14 w-14 rounded-full object-cover sm:right-2 sm:top-5 sm:h-16 sm:w-16"
      height={64}
      src="/alpha-clinic-logo.png"
      width={64}
    />
  );
}

function isAlphaClinic(name: string): boolean {
  return name.trim().toLowerCase() === "alpha clinic";
}

export default function DoctorGate({ children }: Props) {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname() || "";
  const isHomeShell = pathname.startsWith("/home/");
  const [checking, setChecking] = useState(true);
  const [authRequired, setAuthRequired] = useState(false);
  const [clinicGate, setClinicGateState] = useState<ClinicGate | null>(null);
  const [clinicName, setClinicName] = useState("");
  const [clinicPassword, setClinicPassword] = useState("");
  const [showClinicPassword, setShowClinicPassword] = useState(false);
  const [userId, setUserId] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unlocked, setUnlocked] = useState(false);
  const [activeUser, setActiveUser] = useState<ClinicUserInfo | null>(null);
  const [forgotStep, setForgotStep] = useState<ForgotStep>(null);
  const [forgotClinicName, setForgotClinicName] = useState("");
  const [forgotClinicPassword, setForgotClinicPassword] = useState("");
  const [forgotClinicId, setForgotClinicId] = useState("");
  const [forgotDoctors, setForgotDoctors] = useState<ClinicUserInfo[]>([]);
  const [forgotUserId, setForgotUserId] = useState("");
  const [forgotPin, setForgotPin] = useState("");
  const [forgotResetToken, setForgotResetToken] = useState("");
  const [forgotNewPassword, setForgotNewPassword] = useState("");
  const [forgotConfirmPassword, setForgotConfirmPassword] = useState("");
  const [forgotSuccess, setForgotSuccess] = useState(false);
  const [apiServerInput, setApiServerInput] = useState("");

  useEffect(() => {
    setApiServerInput(getApiBaseUrl());
  }, []);

  const showClinicServerField =
    !isProductionApiLocked() &&
    (isNativeApp() ||
      needsClinicUrlSetup() ||
      isLoopbackApiBaseUrl(getApiBaseUrl()));

  const refreshAuth = useCallback(async () => {
    setChecking(true);
    setError(null);
    try {
      const status = await fetchAuthStatus();
      setAuthRequired(status.auth_required);

      if (!status.auth_required) {
        const openGate: ClinicGate = {
          clinic_id: "default",
          name: "Local clinic",
          features: [...ALL_CLINIC_FEATURES],
          users: [
            {
              clinic_id: "default",
              user_id: "local",
              display_name: "Local doctor",
              role: "doctor",
            },
          ],
        };
        setClinicGate(openGate);
        setClinicGateState(openGate);
        setUnlocked(true);
        setActiveUser(openGate.users[0]);
        return;
      }

      const existingGate = getClinicGate();
      setClinicGateState(existingGate);
      if (existingGate?.users?.length) {
        const ordered = sortUsersForSignIn(existingGate.users);
        setUserId((prev) =>
          ordered.some((u) => u.user_id === prev)
            ? prev
            : ordered[0]?.user_id || "",
        );
      }

      const me = await fetchAuthMe();
      if (me.authenticated && getDoctorSession()) {
        const user: ClinicUserInfo = {
          clinic_id: me.clinic_id || existingGate?.clinic_id || "default",
          user_id: me.user_id || "local",
          display_name: me.display_name || "Signed in",
          role: me.role || "doctor",
        };
        // Restore gate branding if missing but session valid
        if (!existingGate && me.clinic_id) {
          const restored: ClinicGate = {
            clinic_id: me.clinic_id,
            name: me.clinic_id,
            features: [...ALL_CLINIC_FEATURES],
            users: [user],
          };
          setClinicGate(restored);
          setClinicGateState(restored);
        }
        setActiveUser(user);
        setUnlocked(true);
        return;
      }

      const existing = getClinicUser();
      const hasSession = !!getDoctorSession();
      setUnlocked(hasSession && !!existing);
      setActiveUser(hasSession ? existing : null);
    } catch (err) {
      setAuthRequired(true);
      setUnlocked(false);
      setActiveUser(null);
      setError(
        "Could not reach the clinic server. Check your network connection and try again.",
      );
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void refreshAuth();
  }, [refreshAuth]);

  const onSaveApiServer = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setApiBaseUrl(apiServerInput);
      setApiServerInput(getApiBaseUrl());
      await refreshAuth();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not save server address",
      );
    } finally {
      setBusy(false);
    }
  }, [apiServerInput, refreshAuth]);

  const onClinicContinue = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        const gate = await unlockClinic(clinicName, clinicPassword);
        setClinicGateState(gate);
        setClinicPassword("");
        setShowClinicPassword(false);
        const ordered = sortUsersForSignIn(gate.users);
        if (ordered[0]) setUserId(ordered[0].user_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Clinic unlock failed");
      } finally {
        setBusy(false);
      }
    },
    [clinicName, clinicPassword],
  );

  const onUnlock = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      if (!clinicGate) return;
      setBusy(true);
      setError(null);
      try {
        const user = await unlockClinicUser(
          userId,
          pin,
          clinicGate.clinic_id,
          clinicGate.clinic_ticket,
        );
        setActiveUser(user);
        setUnlocked(true);
        setPin("");
        router.replace(HOME_LANDING);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Sign-in failed");
      } finally {
        setBusy(false);
      }
    },
    [clinicGate, pin, router, userId],
  );

  const onLock = useCallback(async () => {
    await lockDoctorSession();
    setUnlocked(false);
    setActiveUser(null);
    setPin("");
    setError(null);
    setClinicGateState(getClinicGate());
    try {
      (
        window as unknown as { __healthcareClearPatient?: () => void }
      ).__healthcareClearPatient?.();
    } catch {
      /* ignore */
    }
  }, []);

  const onSwitchClinic = useCallback(async () => {
    await switchClinic();
    setUnlocked(false);
    setActiveUser(null);
    setClinicGateState(null);
    setClinicName("");
    setClinicPassword("");
    setShowClinicPassword(false);
    setPin("");
    setUserId("");
    setError(null);
    setForgotStep(null);
    try {
      (
        window as unknown as { __healthcareClearPatient?: () => void }
      ).__healthcareClearPatient?.();
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    (
      window as unknown as {
        __healthcareSignOut?: () => Promise<void>;
        __healthcareSwitchClinic?: () => Promise<void>;
      }
    ).__healthcareSignOut = onLock;
    (
      window as unknown as {
        __healthcareSignOut?: () => Promise<void>;
        __healthcareSwitchClinic?: () => Promise<void>;
      }
    ).__healthcareSwitchClinic = onSwitchClinic;
    return () => {
      delete (
        window as unknown as { __healthcareSignOut?: () => Promise<void> }
      ).__healthcareSignOut;
      delete (
        window as unknown as { __healthcareSwitchClinic?: () => Promise<void> }
      ).__healthcareSwitchClinic;
    };
  }, [onLock, onSwitchClinic]);

  const resetForgotFlow = useCallback(() => {
    setForgotStep(null);
    setForgotClinicName("");
    setForgotClinicPassword("");
    setForgotClinicId("");
    setForgotDoctors([]);
    setForgotUserId("");
    setForgotPin("");
    setForgotResetToken("");
    setForgotNewPassword("");
    setForgotConfirmPassword("");
    setError(null);
  }, []);

  const onForgotPreview = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        const preview = await previewClinicPasswordDoctors(
          forgotClinicName,
          forgotClinicPassword,
        );
        if (!preview.doctors.length) {
          setError(
            "No doctor profiles for this clinic. Only a doctor can reset the clinic password.",
          );
          return;
        }
        setForgotClinicId(preview.clinic_id);
        setForgotDoctors(preview.doctors);
        setForgotUserId(preview.doctors[0].user_id);
        setForgotStep("doctor");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Clinic not found");
      } finally {
        setBusy(false);
      }
    },
    [forgotClinicName, forgotClinicPassword],
  );

  const onForgotRecover = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        const recovered = await recoverClinicPassword(
          forgotClinicName,
          forgotUserId,
          forgotPin,
        );
        setForgotResetToken(recovered.reset_token);
        setForgotClinicId(recovered.clinic_id);
        setForgotPin("");
        setForgotStep("password");
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to verify clinic recovery details",
        );
      } finally {
        setBusy(false);
      }
    },
    [forgotClinicName, forgotPin, forgotUserId],
  );

  const onForgotReset = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      if (forgotNewPassword !== forgotConfirmPassword) {
        setError("New password and confirmation do not match");
        return;
      }
      if (forgotNewPassword.trim().length < 6) {
        setError("New clinic password must be at least 6 characters");
        return;
      }
      setBusy(true);
      setError(null);
      try {
        await resetClinicPassword(forgotResetToken, forgotNewPassword.trim());
        setClinicName(forgotClinicName);
        resetForgotFlow();
        setForgotSuccess(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not reset password");
      } finally {
        setBusy(false);
      }
    },
    [
      forgotConfirmPassword,
      forgotClinicName,
      forgotNewPassword,
      forgotResetToken,
      resetForgotFlow,
    ],
  );

  if (checking && !error) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center px-4">
        <p className="text-sm text-slate-500">Loading…</p>
      </div>
    );
  }

  if (authRequired && !unlocked) {
    // Forgot clinic password — self-serve via doctor PIN
    if (forgotStep && !clinicGate) {
      const tile =
        "flex flex-col gap-4 rounded-2xl border border-slate-300 bg-slate-200/40 px-5 py-6 shadow-sm";
      const field =
        "mt-2 min-h-12 w-full rounded-lg border-0 bg-white px-4 text-sm text-slate-900 outline-none ring-2 ring-transparent focus:ring-slate-400";
      const primaryBtn =
        "mt-2 inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-white px-4 text-sm font-semibold text-slate-900 disabled:opacity-60";

      return (
        <section
          aria-label="Forgot clinic password"
          className="relative mx-auto flex min-h-[70vh] w-full max-w-md flex-col justify-center gap-6 px-1 py-6"
        >
          <BrandLogoTile />

          {forgotStep === "clinic" ? (
            <form className={tile} onSubmit={onForgotPreview}>
              <p className="text-center text-sm font-medium text-slate-700">
                Forgot clinic password
              </p>
              <p className="text-center text-xs text-slate-600">
                Enter clinic name and current clinic password. A doctor will then
                confirm with their personal PIN to set a new password.
              </p>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Clinic name
                <input
                  aria-label="Clinic name"
                  autoCapitalize="words"
                  className={field}
                  onChange={(e) => setForgotClinicName(e.target.value)}
                  placeholder="Alpha Clinic"
                  value={forgotClinicName}
                />
              </label>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Current clinic password
                <input
                  aria-label="Current clinic password"
                  autoComplete="current-password"
                  className={field}
                  onChange={(e) => setForgotClinicPassword(e.target.value)}
                  type="password"
                  value={forgotClinicPassword}
                />
              </label>
              <button
                className={primaryBtn}
                disabled={
                  busy || !forgotClinicName.trim() || !forgotClinicPassword.trim()
                }
                type="submit"
              >
                {busy ? "Please wait…" : "Continue"}
              </button>
              <button
                className="text-sm text-slate-600 underline-offset-2 hover:underline"
                onClick={() => resetForgotFlow()}
                type="button"
              >
                Back to sign in
              </button>
              {error ? (
                <p className="text-sm text-amber-700" role="alert">
                  {error}
                </p>
              ) : null}
            </form>
          ) : null}

          {forgotStep === "doctor" ? (
            <form className={tile} onSubmit={onForgotRecover}>
              <p className="text-center text-sm font-medium text-slate-700">
                Verify doctor PIN
              </p>
              <p className="text-center text-xs text-slate-600">
                {forgotClinicName}
                {forgotClinicId ? ` · ${forgotClinicId}` : ""}
              </p>
              <fieldset>
                <legend className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Doctor profile
                </legend>
                <ul className="mt-3 space-y-2">
                  {forgotDoctors.map((u) => {
                    const selectedProfile = u.user_id === forgotUserId;
                    return (
                      <li key={`${u.clinic_id || "default"}:${u.user_id}`}>
                        <button
                          aria-pressed={selectedProfile}
                          className={`flex w-full min-h-12 flex-col items-start rounded-lg border px-4 py-3 text-left ${
                            selectedProfile
                              ? "border-slate-400 bg-white ring-1 ring-slate-300"
                              : "border-transparent bg-white/70"
                          }`}
                          onClick={() => setForgotUserId(u.user_id)}
                          type="button"
                        >
                          <span className="text-sm font-medium text-slate-900">
                            {u.display_name}
                          </span>
                          <span className="text-xs text-slate-600">Doctor</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </fieldset>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Personal PIN
                <input
                  aria-label="Doctor PIN"
                  autoComplete="current-password"
                  className={field}
                  inputMode="numeric"
                  onChange={(e) => setForgotPin(e.target.value)}
                  placeholder="Enter your PIN"
                  type="password"
                  value={forgotPin}
                />
              </label>
              <button
                className={primaryBtn}
                disabled={busy || !forgotUserId || !forgotPin.trim()}
                type="submit"
              >
                {busy ? "Please wait…" : "Verify"}
              </button>
              <button
                className="text-sm text-slate-600 underline-offset-2 hover:underline"
                onClick={() => {
                  setForgotStep("clinic");
                  setForgotPin("");
                  setError(null);
                }}
                type="button"
              >
                Back
              </button>
              {error ? (
                <p className="text-sm text-amber-700" role="alert">
                  {error}
                </p>
              ) : null}
            </form>
          ) : null}

          {forgotStep === "password" ? (
            <form className={tile} onSubmit={onForgotReset}>
              <p className="text-center text-sm font-medium text-slate-700">
                Set new clinic password
              </p>
              <p className="text-center text-xs text-slate-600">
                At least 6 characters. You will use this to unlock the clinic.
              </p>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                New clinic password
                <input
                  aria-label="New clinic password"
                  autoComplete="new-password"
                  className={field}
                  onChange={(e) => setForgotNewPassword(e.target.value)}
                  type="password"
                  value={forgotNewPassword}
                />
              </label>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Confirm password
                <input
                  aria-label="Confirm clinic password"
                  autoComplete="new-password"
                  className={field}
                  onChange={(e) => setForgotConfirmPassword(e.target.value)}
                  type="password"
                  value={forgotConfirmPassword}
                />
              </label>
              <button
                className={primaryBtn}
                disabled={
                  busy ||
                  !forgotNewPassword.trim() ||
                  !forgotConfirmPassword.trim()
                }
                type="submit"
              >
                {busy ? "Please wait…" : "Save password"}
              </button>
              <button
                className="text-sm text-slate-600 underline-offset-2 hover:underline"
                onClick={() => resetForgotFlow()}
                type="button"
              >
                Cancel
              </button>
              {error ? (
                <p className="text-sm text-amber-700" role="alert">
                  {error}
                </p>
              ) : null}
            </form>
          ) : null}
        </section>
      );
    }

    // Step 1 — clinic name + password (wireframe)
    if (!clinicGate) {
      return (
        <section
          aria-label="Clinic unlock"
          className="relative mx-auto flex min-h-[70vh] w-full max-w-md flex-col justify-center gap-6 px-1 py-6"
        >
          <BrandLogoTile />

          <form
            className="flex flex-col gap-4 rounded-2xl border border-slate-300 bg-slate-200/40 px-5 py-6 shadow-sm"
            onSubmit={onClinicContinue}
          >
            <p className="text-center text-sm font-medium text-slate-700">
              Clinic name &amp; password
            </p>
            {showClinicServerField ? (
              <div className="rounded-lg border border-slate-200 bg-white/80 px-3 py-3">
                {needsClinicUrlSetup() ? (
                  <p className="text-sm text-amber-800" role="alert">
                    {t("clinicServerLoopback")}
                  </p>
                ) : null}
                <label className="mt-2 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("clinicServer")}
                  <input
                    aria-label={t("clinicServer")}
                    autoCapitalize="none"
                    autoCorrect="off"
                    className="mt-2 min-h-12 w-full rounded-lg border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none ring-2 ring-transparent focus:ring-slate-400"
                    onChange={(e) => setApiServerInput(e.target.value)}
                    placeholder={getDefaultApiBaseUrl()}
                    spellCheck={false}
                    type="url"
                    value={apiServerInput}
                  />
                </label>
                <p className="mt-1 text-xs text-slate-500">{t("clinicServerHint")}</p>
                <button
                  className="mt-3 inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 disabled:opacity-60"
                  disabled={busy || !apiServerInput.trim()}
                  onClick={() => void onSaveApiServer()}
                  type="button"
                >
                  {busy ? "Please wait…" : t("saveReconnect")}
                </button>
              </div>
            ) : null}
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Clinic name
              <input
                aria-label="Clinic name"
                autoCapitalize="words"
                className="mt-2 min-h-12 w-full rounded-lg border-0 bg-white px-4 text-sm text-slate-900 outline-none ring-2 ring-transparent focus:ring-slate-400"
                onChange={(e) => setClinicName(e.target.value)}
                placeholder="Alpha Clinic"
                value={clinicName}
              />
            </label>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Clinic password
              <span className="relative mt-2 block">
                <input
                  aria-label="Clinic password"
                  autoComplete="current-password"
                  className="min-h-12 w-full rounded-lg border-0 bg-white py-3 pl-4 pr-12 text-sm text-slate-900 outline-none ring-2 ring-transparent focus:ring-slate-400"
                  onChange={(e) => setClinicPassword(e.target.value)}
                  placeholder="Enter clinic password"
                  type={showClinicPassword ? "text" : "password"}
                  value={clinicPassword}
                />
                <button
                  aria-label={
                    showClinicPassword
                      ? "Hide clinic password"
                      : "Show clinic password"
                  }
                  aria-pressed={showClinicPassword}
                  className="absolute inset-y-0 right-0 inline-flex w-12 items-center justify-center rounded-r-lg text-slate-500 hover:text-slate-800"
                  onClick={() => setShowClinicPassword((v) => !v)}
                  type="button"
                >
                  {showClinicPassword ? (
                    <svg
                      aria-hidden="true"
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      viewBox="0 0 24 24"
                    >
                      <path
                        d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    <svg
                      aria-hidden="true"
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      viewBox="0 0 24 24"
                    >
                      <path
                        d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>
              </span>
            </label>
            <button
              className="mt-2 inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-white px-4 text-sm font-semibold text-slate-900 disabled:opacity-60"
              disabled={busy || !clinicName.trim() || !clinicPassword.trim()}
              type="submit"
            >
              {busy ? "Please wait…" : "Continue"}
            </button>
            <button
              className="text-center text-sm text-slate-600 underline-offset-2 hover:underline"
              onClick={() => {
                setForgotStep("clinic");
                setForgotClinicName(clinicName);
                setForgotSuccess(false);
                setError(null);
              }}
              type="button"
            >
              Forgot clinic password?
            </button>
            {forgotSuccess ? (
              <p className="text-sm text-emerald-700" role="status">
                Clinic password updated. Sign in with the new password.
              </p>
            ) : null}
            {error ? (
              <p className="text-sm text-amber-700" role="alert">
                {error}
              </p>
            ) : null}
          </form>
        </section>
      );
    }

    // Step 2 — profile + personal PIN
    const clinicUsers = sortUsersForSignIn(clinicGate.users);
    const selected =
      clinicUsers.find((u) => u.user_id === userId) ?? clinicUsers[0] ?? null;

    return (
      <section
        aria-label="Clinic sign-in"
        className="relative mx-auto flex w-full max-w-md flex-col px-1 py-4"
      >
        {isAlphaClinic(clinicGate.name) ? <AlphaClinicLogoCorner /> : null}
        <p className="pr-16 text-sm uppercase tracking-[0.2em] text-slate-500 sm:pr-20">
          Aarogya One Connect
        </p>
        <h1 className="mt-4 pr-16 text-3xl font-semibold tracking-tight text-slate-900 sm:pr-20">
          Sign in
        </h1>
        <p className="mt-2 text-base text-slate-600">
          {clinicGate.name}
          {clinicGate.address ? ` · ${clinicGate.address}` : ""}
        </p>
        <p className="mt-1 text-sm text-slate-500">
          Choose your profile, then enter your PIN.
        </p>

        <form className="mt-8 flex flex-col gap-5" onSubmit={onUnlock}>
          <fieldset>
            <legend className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Your profile
            </legend>
            <ul className="mt-3 space-y-2">
              {clinicUsers.map((u) => {
                const selectedProfile = u.user_id === userId;
                return (
                  <li key={`${u.clinic_id || "default"}:${u.user_id}`}>
                    <button
                      aria-pressed={selectedProfile}
                      className={`flex w-full min-h-14 flex-col items-start rounded-xl border px-4 py-3 text-left transition ${
                        selectedProfile
                          ? "border-slate-300 bg-slate-200/40 ring-1 ring-slate-300"
                          : "border-slate-200 bg-white hover:border-slate-300"
                      }`}
                      onClick={() => setUserId(u.user_id)}
                      type="button"
                    >
                      <span className="text-sm font-medium text-slate-900">
                        {u.display_name}
                      </span>
                      <span className="mt-0.5 text-xs text-slate-600">
                        {roleLabel(u.role)} · {roleHint(u.role)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {clinicUsers.length === 0 ? (
              <p className="mt-3 text-sm text-amber-700">
                No profiles for this clinic. Check CLINIC_USERS on the server.
              </p>
            ) : null}
          </fieldset>

          {selected ? (
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
              Signing in as{" "}
              <span className="font-medium">{selected.display_name}</span> (
              {roleLabel(selected.role)})
            </p>
          ) : null}

          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
            PIN
            <input
              aria-label="Clinic PIN"
              autoComplete="current-password"
              className="mt-2 min-h-12 w-full rounded-lg border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none ring-clinical-500 focus:ring-2"
              inputMode="numeric"
              onChange={(e) => setPin(e.target.value)}
              placeholder="Enter your PIN"
              type="password"
              value={pin}
            />
          </label>

          <button
            className="inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-clinical-500 px-4 text-sm font-medium text-white disabled:opacity-60"
            disabled={busy || !pin.trim() || !userId}
            type="submit"
          >
            {busy ? "Please wait…" : "Sign in"}
          </button>
        </form>

        <button
          className="mt-4 text-sm text-slate-600 underline-offset-2 hover:underline"
          onClick={() => void onSwitchClinic()}
          type="button"
        >
          Switch clinic
        </button>

        {error ? (
          <p className="mt-4 text-sm text-red-600" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    );
  }

  return (
    <div className="space-y-6">
      {!isHomeShell ? (
      <header className="border-b border-slate-100 pb-4 dark:border-slate-800">
        <div className="min-w-0">
          <p className="text-sm uppercase tracking-[0.2em] text-slate-500">
            Aarogya One Connect
          </p>
          <h1 className="mt-2 text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">
            {activeUser?.role === "lab"
              ? "Lab desk"
              : activeUser?.role === "receptionist"
                ? "Reception desk"
                : activeUser?.role === "staff"
                  ? "Staff desk"
                  : "Doctor desk"}
          </h1>
          <p className="mt-1 truncate text-sm text-slate-600">
            {clinicGate?.name ? `${clinicGate.name} · ` : ""}
            {activeUser
              ? `${activeUser.display_name} · ${roleLabel(activeUser.role)}`
              : "Signed in"}
          </p>
        </div>
        {authRequired ? (
          <div className="mt-3 flex flex-wrap justify-end gap-2">
            <button
              className="inline-flex min-h-12 shrink-0 items-center rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-800"
              onClick={() => void onSwitchClinic()}
              type="button"
            >
              Switch clinic
            </button>
            <button
              className="inline-flex min-h-12 shrink-0 items-center rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-800"
              onClick={() => void onLock()}
              type="button"
            >
              {t("signOut")}
            </button>
          </div>
        ) : null}
      </header>
      ) : null}
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

export function useActiveClinicRole(): ClinicRole {
  const [role, setRole] = useState<ClinicRole>(() => {
    const r = getClinicUser()?.role;
    if (r === "staff" || r === "lab" || r === "receptionist") return r;
    return "doctor";
  });
  useEffect(() => {
    const user = getClinicUser();
    if (
      user?.role === "staff" ||
      user?.role === "lab" ||
      user?.role === "receptionist"
    ) {
      setRole(user.role);
    } else {
      setRole("doctor");
    }
  }, []);
  return role;
}

export function useClinicFeatures(): {
  has: (feature: ClinicFeature) => boolean;
  features: ClinicFeature[];
} {
  const [features, setFeatures] = useState<ClinicFeature[]>(() => {
    const gate = getClinicGate();
    return gate?.features?.length
      ? gate.features
      : [...ALL_CLINIC_FEATURES];
  });

  useEffect(() => {
    const gate = getClinicGate();
    setFeatures(
      gate?.features?.length ? gate.features : [...ALL_CLINIC_FEATURES],
    );
  }, []);

  return {
    features,
    has: (feature: ClinicFeature) => features.includes(feature),
  };
}
