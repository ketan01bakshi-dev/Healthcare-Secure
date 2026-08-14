export interface AuthUser {
  id: number;
  email: string;
  role: "admin" | "clinician";
}

export interface Patient {
  id: number;
  fullName: string;
  dateOfBirth: string;
  medicalRecord: string;
  createdBy: number;
  createdAt: string;
  updatedAt: string;
}

async function request<T>(url: string, options: RequestInit & { token?: string } = {}): Promise<T> {
  const { token, headers, ...rest } = options;
  const res = await fetch(url, {
    ...rest,
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new Error(data?.error ?? `Request failed (${res.status})`);
  }
  return data as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ token: string; user: AuthUser }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, role?: string) =>
    request<{ token: string; user: AuthUser }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, role }),
    }),
  listPatients: (token: string) =>
    request<{ patients: Patient[] }>("/api/patients", { token }),
  createPatient: (
    token: string,
    payload: { fullName: string; dateOfBirth: string; medicalRecord: string }
  ) =>
    request<{ patient: Patient }>("/api/patients", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
};
