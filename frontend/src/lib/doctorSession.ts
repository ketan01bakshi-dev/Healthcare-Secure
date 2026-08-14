import { getApiBaseUrl, isLoopbackApiBaseUrl } from "@/lib/apiBase";

const SESSION_KEY = "healthcare_doctor_session";
const USER_KEY = "healthcare_clinic_user";
const CLINIC_GATE_KEY = "healthcare_clinic_gate";

export type ClinicRole = "doctor" | "staff" | "lab" | "receptionist";

export type ClinicFeature =
  | "voice_rx"
  | "labs"
  | "queue"
  | "appointments"
  | "analytics"
  | "obstetric"
  | "video_consult";

export const ALL_CLINIC_FEATURES: ClinicFeature[] = [
  "voice_rx",
  "labs",
  "queue",
  "appointments",
  "analytics",
  "obstetric",
  "video_consult",
];

export type ClinicUserInfo = {
  clinic_id?: string;
  user_id: string;
  display_name: string;
  role: ClinicRole;
};

export type ClinicInfo = {
  clinic_id: string;
  name: string;
};

export type ClinicGate = {
  clinic_id: string;
  name: string;
  address?: string;
  subtitle?: string;
  features: ClinicFeature[];
  users: ClinicUserInfo[];
  /** Short-lived server ticket from clinic-unlock; required for PIN unlock. */
  clinic_ticket?: string;
};

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage;
  } catch {
    return null;
  }
}

/** Migrate sessionStorage → localStorage once (older APKs). */
function migrateFromSession(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    const fromLocal = localStorage.getItem(key);
    if (fromLocal) return fromLocal;
    const fromSession = sessionStorage.getItem(key);
    if (fromSession) {
      localStorage.setItem(key, fromSession);
      sessionStorage.removeItem(key);
      return fromSession;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function normalizeClinicRole(role: string | undefined | null): ClinicRole {
  if (role === "staff") return "staff";
  if (role === "lab" || role === "diagnostic") return "lab";
  if (
    role === "receptionist" ||
    role === "reception" ||
    role === "front_desk" ||
    role === "frontdesk"
  ) {
    return "receptionist";
  }
  return "doctor";
}

function normalizeFeatures(raw: unknown): ClinicFeature[] {
  if (!Array.isArray(raw) || raw.length === 0) {
    return [...ALL_CLINIC_FEATURES];
  }
  const allowed = new Set<string>(ALL_CLINIC_FEATURES);
  const out = raw
    .map((f) => String(f).trim().toLowerCase())
    .filter((f): f is ClinicFeature => allowed.has(f));
  return out.length ? out : [...ALL_CLINIC_FEATURES];
}

export function getDoctorSession(): string | null {
  return migrateFromSession(SESSION_KEY);
}

export function setDoctorSession(token: string | null) {
  const store = storage();
  if (!store) return;
  if (token) store.setItem(SESSION_KEY, token);
  else store.removeItem(SESSION_KEY);
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

export function getClinicUser(): ClinicUserInfo | null {
  const raw = migrateFromSession(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ClinicUserInfo;
  } catch {
    return null;
  }
}

export function setClinicUser(user: ClinicUserInfo | null) {
  const store = storage();
  if (!store) return;
  if (user) store.setItem(USER_KEY, JSON.stringify(user));
  else store.removeItem(USER_KEY);
  try {
    sessionStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

export function getClinicGate(): ClinicGate | null {
  const store = storage();
  if (!store) return null;
  try {
    const raw = store.getItem(CLINIC_GATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ClinicGate;
    if (!parsed?.clinic_id || !parsed?.name) return null;
    return {
      ...parsed,
      features: normalizeFeatures(parsed.features),
      users: Array.isArray(parsed.users) ? parsed.users : [],
    };
  } catch {
    return null;
  }
}

export function setClinicGate(gate: ClinicGate | null) {
  const store = storage();
  if (!store) return;
  if (gate) {
    store.setItem(
      CLINIC_GATE_KEY,
      JSON.stringify({
        ...gate,
        features: normalizeFeatures(gate.features),
      }),
    );
  } else {
    store.removeItem(CLINIC_GATE_KEY);
  }
}

export function clearClinicGate() {
  setClinicGate(null);
}

export function isDoctorRole(): boolean {
  const user = getClinicUser();
  if (!user) {
    return true;
  }
  return user.role === "doctor";
}

export function clinicHasFeature(feature: ClinicFeature): boolean {
  const gate = getClinicGate();
  if (!gate) return true;
  return gate.features.includes(feature);
}

export function authHeaders(extra?: HeadersInit): Record<string, string> {
  const headers: Record<string, string> = {};
  if (extra) {
    const h = new Headers(extra);
    h.forEach((value, key) => {
      headers[key] = value;
    });
  }
  const session = getDoctorSession();
  if (session) {
    headers["X-Doctor-Session"] = session;
  }
  return headers;
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const base = getApiBaseUrl();
  const url = path.startsWith("http") ? path : `${base}${path}`;
  const headers = authHeaders(init.headers);
  if (init.body instanceof FormData) {
    delete headers["Content-Type"];
  } else if (
    !headers["Content-Type"] &&
    init.body &&
    typeof init.body === "string"
  ) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(url, { ...init, headers });
}

export async function fetchAuthMe(): Promise<{
  authenticated: boolean;
  clinic_id?: string;
  user_id?: string;
  display_name?: string;
  role?: ClinicRole;
}> {
  const session = getDoctorSession();
  if (!session) return { authenticated: false };
  try {
    const response = await apiFetch("/api/v1/auth/me");
    if (!response.ok) return { authenticated: false };
    const data = (await response.json()) as {
      authenticated?: boolean;
      clinic_id?: string;
      user_id?: string;
      display_name?: string;
      role?: ClinicRole;
    };
    return {
      authenticated: !!data.authenticated,
      clinic_id: data.clinic_id,
      user_id: data.user_id,
      display_name: data.display_name,
      role: data.role ? normalizeClinicRole(data.role) : undefined,
    };
  } catch {
    return { authenticated: false };
  }
}

export async function fetchAuthStatus(): Promise<{
  auth_required: boolean;
  users: ClinicUserInfo[];
  clinics: ClinicInfo[];
}> {
  const url = `${getApiBaseUrl()}/api/v1/auth/status`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      return { auth_required: false, users: [], clinics: [] };
    }
    const data = (await response.json()) as {
      auth_required?: boolean;
      users?: ClinicUserInfo[];
      clinics?: ClinicInfo[];
    };
    // Status no longer returns roster (share lockdown) — keep empty arrays.
    return {
      auth_required: !!data.auth_required,
      users: Array.isArray(data.users) ? data.users : [],
      clinics: Array.isArray(data.clinics) ? data.clinics : [],
    };
  } catch (err) {
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  const text = await response.text().catch(() => "");
  let detail = text || fallback;
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (typeof parsed.detail === "string") detail = parsed.detail;
  } catch {
    /* keep */
  }
  return detail;
}

export async function previewClinicPasswordDoctors(
  clinicName: string,
  password: string,
): Promise<{ clinic_id: string; name: string; doctors: ClinicUserInfo[] }> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/auth/clinic-password/preview`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_name: clinicName.trim(),
        password,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(await readApiError(response, "Unknown clinic"));
  }
  const data = (await response.json()) as {
    clinic_id?: string;
    name?: string;
    doctors?: ClinicUserInfo[];
  };
  return {
    clinic_id: data.clinic_id || "default",
    name: data.name || clinicName.trim(),
    doctors: Array.isArray(data.doctors)
      ? data.doctors.map((u) => ({
          ...u,
          role: normalizeClinicRole(u.role),
        }))
      : [],
  };
}

export async function recoverClinicPassword(
  clinicName: string,
  userId: string,
  pin: string,
): Promise<{ reset_token: string; clinic_id: string }> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/auth/clinic-password/recover`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_name: clinicName.trim(),
        user_id: userId,
        pin,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(
      await readApiError(response, "Unable to verify clinic recovery details"),
    );
  }
  const data = (await response.json()) as {
    reset_token?: string;
    clinic_id?: string;
  };
  if (!data.reset_token) {
    throw new Error("Recovery failed. Try again.");
  }
  return {
    reset_token: data.reset_token,
    clinic_id: data.clinic_id || "default",
  };
}

export async function resetClinicPassword(
  resetToken: string,
  newPassword: string,
): Promise<void> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/auth/clinic-password/reset`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reset_token: resetToken,
        new_password: newPassword,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(await readApiError(response, "Could not reset password"));
  }
}

export async function unlockClinic(
  clinicName: string,
  password: string,
): Promise<ClinicGate> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/clinic-unlock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      clinic_name: clinicName.trim(),
      password,
    }),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Invalid clinic password"));
  }
  const data = (await response.json()) as {
    clinic_id?: string;
    name?: string;
    address?: string;
    subtitle?: string;
    features?: string[];
    users?: ClinicUserInfo[];
    clinic_ticket?: string;
  };
  const gate: ClinicGate = {
    clinic_id: data.clinic_id || "default",
    name: data.name || clinicName.trim(),
    address: data.address || "",
    subtitle: data.subtitle || "",
    features: normalizeFeatures(data.features),
    users: Array.isArray(data.users)
      ? data.users.map((u) => ({
          ...u,
          role: normalizeClinicRole(u.role),
        }))
      : [],
    clinic_ticket: data.clinic_ticket || "",
  };
  setClinicGate(gate);
  return gate;
}

export async function unlockClinicUser(
  userId: string,
  pin: string,
  clinicId?: string | null,
  clinicTicket?: string | null,
): Promise<ClinicUserInfo> {
  const ticket = clinicTicket || getClinicGate()?.clinic_ticket || "";
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/unlock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      pin,
      clinic_id: clinicId || undefined,
      clinic_ticket: ticket || undefined,
    }),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Invalid PIN"));
  }
  const data = (await response.json()) as {
    session_token?: string | null;
    clinic_id?: string;
    user_id?: string;
    display_name?: string;
    role?: ClinicRole;
    auth_required?: boolean;
  };
  if (data.session_token) {
    setDoctorSession(data.session_token);
  } else {
    setDoctorSession(null);
  }
  const user: ClinicUserInfo = {
    clinic_id: data.clinic_id || clinicId || "default",
    user_id: data.user_id || userId,
    display_name: data.display_name || userId,
    role: normalizeClinicRole(data.role),
  };
  setClinicUser(user);
  return user;
}

/** @deprecated use unlockClinicUser */
export async function unlockWithPin(pin: string): Promise<string | null> {
  const status = await fetchAuthStatus();
  const doctor =
    status.users.find((u) => u.role === "doctor") || status.users[0];
  if (!doctor) {
    setDoctorSession(null);
    setClinicUser({
      clinic_id: "default",
      user_id: "local",
      display_name: "Local doctor",
      role: "doctor",
    });
    return null;
  }
  await unlockClinicUser(
    doctor.user_id,
    pin,
    doctor.clinic_id,
    getClinicGate()?.clinic_ticket,
  );
  return getDoctorSession();
}

export async function lockDoctorSession(): Promise<void> {
  try {
    await fetch(`${getApiBaseUrl()}/api/v1/auth/lock`, {
      method: "POST",
      headers: authHeaders(),
    });
  } finally {
    setDoctorSession(null);
    setClinicUser(null);
    // Keep clinic gate so re-sign-in only needs personal PIN.
  }
}

export async function switchClinic(): Promise<void> {
  try {
    await fetch(`${getApiBaseUrl()}/api/v1/auth/lock`, {
      method: "POST",
      headers: authHeaders(),
    });
  } finally {
    setDoctorSession(null);
    setClinicUser(null);
    clearClinicGate();
  }
}
