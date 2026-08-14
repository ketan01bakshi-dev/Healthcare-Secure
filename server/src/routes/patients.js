import { Router } from "express";
import { z } from "zod";
import { db, recordAudit } from "../db.js";
import { authenticate, requireRole } from "../middleware/authenticate.js";

export const patientsRouter = Router();

patientsRouter.use(authenticate);

const patientSchema = z.object({
  fullName: z.string().min(1).max(200),
  dateOfBirth: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Expected YYYY-MM-DD"),
  medicalRecord: z.string().max(5000).optional().default(""),
});

function serialize(row) {
  return {
    id: row.id,
    fullName: row.full_name,
    dateOfBirth: row.date_of_birth,
    medicalRecord: row.medical_record,
    createdBy: row.created_by,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

patientsRouter.get("/", (req, res) => {
  const rows = db.prepare("SELECT * FROM patients ORDER BY created_at DESC, id DESC").all();
  res.json({ patients: rows.map(serialize) });
});

patientsRouter.get("/:id", (req, res) => {
  const id = Number(req.params.id);
  const row = db.prepare("SELECT * FROM patients WHERE id = ?").get(id);
  if (!row) return res.status(404).json({ error: "Patient not found." });
  res.json({ patient: serialize(row) });
});

patientsRouter.post("/", (req, res) => {
  const parsed = patientSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: "Invalid input.", details: parsed.error.flatten() });
  }
  const { fullName, dateOfBirth, medicalRecord } = parsed.data;
  const result = db
    .prepare(
      "INSERT INTO patients (full_name, date_of_birth, medical_record, created_by) VALUES (?, ?, ?, ?)"
    )
    .run(fullName, dateOfBirth, medicalRecord, req.user.id);
  const row = db.prepare("SELECT * FROM patients WHERE id = ?").get(result.lastInsertRowid);
  recordAudit(req.user.id, "patient.create", `patient:${row.id}`);
  res.status(201).json({ patient: serialize(row) });
});

patientsRouter.delete("/:id", requireRole("admin"), (req, res) => {
  const id = Number(req.params.id);
  const result = db.prepare("DELETE FROM patients WHERE id = ?").run(id);
  if (result.changes === 0) return res.status(404).json({ error: "Patient not found." });
  recordAudit(req.user.id, "patient.delete", `patient:${id}`);
  res.status(204).end();
});
