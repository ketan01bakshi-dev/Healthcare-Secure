import { db, recordAudit } from "./db.js";
import { hashPassword } from "./auth.js";

const DEFAULT_ADMIN_EMAIL = process.env.SEED_ADMIN_EMAIL ?? "admin@healthcare.local";
const DEFAULT_ADMIN_PASSWORD = process.env.SEED_ADMIN_PASSWORD ?? "ChangeMe123!";

async function seed() {
  const existing = db.prepare("SELECT id FROM users WHERE email = ?").get(DEFAULT_ADMIN_EMAIL);
  if (existing) {
    console.log(`Seed admin already exists: ${DEFAULT_ADMIN_EMAIL}`);
    return;
  }

  const passwordHash = await hashPassword(DEFAULT_ADMIN_PASSWORD);
  const result = db
    .prepare("INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'admin')")
    .run(DEFAULT_ADMIN_EMAIL, passwordHash);
  recordAudit(result.lastInsertRowid, "user.seed_admin", DEFAULT_ADMIN_EMAIL);

  console.log("Seeded default admin account:");
  console.log(`  email:    ${DEFAULT_ADMIN_EMAIL}`);
  console.log(`  password: ${DEFAULT_ADMIN_PASSWORD}`);
}

seed()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
