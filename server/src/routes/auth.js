import { Router } from "express";
import { z } from "zod";
import { db, recordAudit } from "../db.js";
import { hashPassword, verifyPassword, issueToken } from "../auth.js";

export const authRouter = Router();

const credentialsSchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(8).max(128),
});

const registerSchema = credentialsSchema.extend({
  role: z.enum(["admin", "clinician"]).optional(),
});

authRouter.post("/register", async (req, res) => {
  const parsed = registerSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: "Invalid input.", details: parsed.error.flatten() });
  }

  const { email, password, role } = parsed.data;
  const existing = db.prepare("SELECT id FROM users WHERE email = ?").get(email);
  if (existing) {
    return res.status(409).json({ error: "An account with that email already exists." });
  }

  const passwordHash = await hashPassword(password);
  const result = db
    .prepare("INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)")
    .run(email, passwordHash, role ?? "clinician");

  const user = { id: result.lastInsertRowid, email, role: role ?? "clinician" };
  recordAudit(user.id, "user.register", email);
  const token = issueToken(user);
  return res.status(201).json({ token, user: { id: user.id, email, role: user.role } });
});

authRouter.post("/login", async (req, res) => {
  const parsed = credentialsSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: "Invalid input." });
  }

  const { email, password } = parsed.data;
  const row = db.prepare("SELECT * FROM users WHERE email = ?").get(email);
  // Always run a comparison to reduce user-enumeration timing differences.
  const ok = row ? await verifyPassword(password, row.password_hash) : await verifyPassword(password, "$2a$12$invalidinvalidinvalidinvalidinvalidinvalidinvalidinv");

  if (!row || !ok) {
    recordAudit(row?.id ?? null, "user.login_failed", email);
    return res.status(401).json({ error: "Invalid credentials." });
  }

  recordAudit(row.id, "user.login", email);
  const token = issueToken(row);
  return res.json({ token, user: { id: row.id, email: row.email, role: row.role } });
});
