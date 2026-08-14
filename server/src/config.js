import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const isProduction = process.env.NODE_ENV === "production";

// In production a strong secret MUST be supplied. For local/dev we fall back to
// a clearly-marked development value so the app is runnable out of the box.
const DEV_SECRET = "dev-only-insecure-secret-change-me";

if (isProduction && !process.env.JWT_SECRET) {
  throw new Error("JWT_SECRET must be set in production environments.");
}

export const config = {
  port: Number(process.env.PORT ?? 3001),
  host: process.env.HOST ?? "0.0.0.0",
  jwtSecret: process.env.JWT_SECRET ?? DEV_SECRET,
  jwtExpiresIn: process.env.JWT_EXPIRES_IN ?? "1h",
  bcryptRounds: Number(process.env.BCRYPT_ROUNDS ?? 12),
  databasePath:
    process.env.DATABASE_PATH ??
    path.join(__dirname, "..", "data", "healthcare.db"),
  isProduction,
};
