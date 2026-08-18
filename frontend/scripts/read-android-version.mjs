/**
 * Read Android version.properties and print values for shell scripts.
 * Usage: node scripts/read-android-version.mjs
 * Prints: VERSION_CODE=N VERSION_NAME=X.Y
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const propsPath = path.join(root, "android", "app", "version.properties");
const text = fs.readFileSync(propsPath, "utf8");
const code = (text.match(/^VERSION_CODE=(.+)$/m) || [])[1]?.trim() || "1";
const name = (text.match(/^VERSION_NAME=(.+)$/m) || [])[1]?.trim() || "1.0";
process.stdout.write(`VERSION_CODE=${code}\nVERSION_NAME=${name}\n`);
