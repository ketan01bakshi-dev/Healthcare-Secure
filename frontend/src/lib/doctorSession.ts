import { API_BASE_URL } from "@/lib/api";

const SESSION_KEY = "healthcare_doctor_session";
const USER_KEY = "healthcare_clinic_user";

export type ClinicRole = "doctor" | "staff";

export type ClinicUserInfo = {
  user_id: string;
  display_name: string;
  role: ClinicRole;
};

export function getDoctorSession(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(SESSION_KEY);
}

export function setDoctorSession(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) sessionStorage.setItem(SESSION_KEY, token);
  else sessionStorage.removeItem(SESSION_KEY);
}

export function getClinicUser(): ClinicUserInfo | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ClinicUserInfo;
  } catch {
    return null;
  }
}

export function setClinicUser(user: ClinicUserInfo | null) {
  if (typeof window === "undefined") return;
  if (user) sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  else sessionStorage.removeItem(USER_KEY);
}

export function isDoctorRole(): boolean {
  const user = getClinicUser();
  if (!user) {
    // Auth disabled / local POC → treat as doctor.
    return true;
  }
  return user.role === "doctor";
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
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
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

export async function fetchAuthStatus(): Promise<{
  auth_required: boolean;
  users: ClinicUserInfo[];
}> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/status`);
  if (!response.ok) {
    return { auth_required: false, users: [] };
  }
  const data = (await response.json()) as {
    auth_required?: boolean;
    users?: ClinicUserInfo[];
  };
  return {
    auth_required: !!data.auth_required,
    users: Array.isArray(data.users) ? data.users : [],
  };
}

export async function unlockClinicUser(
  userId: string,
  pin: string,
): Promise<ClinicUserInfo> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/unlock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, pin }),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || "Invalid PIN");
  }
  const data = (await response.json()) as {
    session_token?: string | null;
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
    user_id: data.user_id || userId,
    display_name: data.display_name || userId,
    role: data.role === "staff" ? "staff" : "doctor",
  };
  setClinicUser(user);
  return user;
}

/** @deprecated use unlockClinicUser */
export async function unlockWithPin(pin: string): Promise<string | null> {
  const status = await fetchAuthStatus();
  const doctor = status.users.find((u) => u.role === "doctor") || status.users[0];
  if (!doctor) {
    setDoctorSession(null);
    setClinicUser({ user_id: "local", display_name: "Local doctor", role: "doctor" });
    return null;
  }
  const user = await unlockClinicUser(doctor.user_id, pin);
  return getDoctorSession();
}

export async function lockDoctorSession(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/v1/auth/lock`, {
      method: "POST",
      headers: authHeaders(),
    });
  } finally {
    setDoctorSession(null);
    setClinicUser(null);
  }
}
