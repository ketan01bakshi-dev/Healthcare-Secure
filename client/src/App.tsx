import { useCallback, useEffect, useState } from "react";
import { api, type AuthUser, type Patient } from "./api";

export function App() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  if (!token || !user) {
    return <Login onAuthenticated={(t, u) => { setToken(t); setUser(u); }} />;
  }

  return (
    <Dashboard
      token={token}
      user={user}
      onLogout={() => {
        setToken(null);
        setUser(null);
      }}
    />
  );
}

function Login({ onAuthenticated }: { onAuthenticated: (token: string, user: AuthUser) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("admin@healthcare.local");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "login"
          ? await api.login(email, password)
          : await api.register(email, password);
      onAuthenticated(result.token, result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-mark">+</span>
          <h1>Healthcare-Secure</h1>
        </div>
        <p className="subtitle">Secure patient records portal</p>

        <div className="tabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
            Sign in
          </button>
          <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} type="button">
            Register
          </button>
        </div>

        <form onSubmit={submit}>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary" type="submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Dashboard({ token, user, onLogout }: { token: string; user: AuthUser; onLogout: () => void }) {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [medicalRecord, setMedicalRecord] = useState("");

  const refresh = useCallback(async () => {
    try {
      const { patients } = await api.listPatients(token);
      setPatients(patients);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load patients");
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function addPatient(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.createPatient(token, { fullName, dateOfBirth, medicalRecord });
      setFullName("");
      setDateOfBirth("");
      setMedicalRecord("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add patient");
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">+</span>
          <strong>Healthcare-Secure</strong>
        </div>
        <div className="user-chip">
          <span className="role-badge">{user.role}</span>
          <span>{user.email}</span>
          <button className="ghost" onClick={onLogout} type="button">Sign out</button>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <h2>Add patient record</h2>
          <form className="patient-form" onSubmit={addPatient}>
            <label>
              Full name
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </label>
            <label>
              Date of birth
              <input
                type="date"
                value={dateOfBirth}
                onChange={(e) => setDateOfBirth(e.target.value)}
                required
              />
            </label>
            <label>
              Medical notes
              <textarea
                value={medicalRecord}
                onChange={(e) => setMedicalRecord(e.target.value)}
                rows={3}
                placeholder="Allergies, conditions, notes…"
              />
            </label>
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary" type="submit">Save record</button>
          </form>
        </section>

        <section className="panel">
          <h2>Patient records <span className="count">{patients.length}</span></h2>
          {patients.length === 0 ? (
            <p className="empty">No patient records yet. Add one to get started.</p>
          ) : (
            <table className="records">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Date of birth</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((p) => (
                  <tr key={p.id}>
                    <td>{p.fullName}</td>
                    <td>{p.dateOfBirth}</td>
                    <td>{p.medicalRecord || <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </div>
  );
}
