/**
 * AGP 9.x rejects getDefaultProguardFile('proguard-android.txt').
 * Capacitor app + some plugins still ship the old name; rewrite before Gradle runs.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

const OLD = "getDefaultProguardFile('proguard-android.txt')";
const NEW = "getDefaultProguardFile('proguard-android-optimize.txt')";

function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const name of fs.readdirSync(dir)) {
    if (name === ".git" || name === "build") continue;
    const p = path.join(dir, name);
    let st;
    try {
      st = fs.statSync(p);
    } catch {
      continue;
    }
    if (st.isDirectory()) walk(p, out);
    else if (name === "build.gradle" || name === "build.gradle.kts") out.push(p);
  }
  return out;
}

const roots = [
  path.join(frontendRoot, "android"),
  path.join(frontendRoot, "node_modules", "@capacitor"),
  path.join(frontendRoot, "node_modules", "@capacitor-community"),
];

let fixed = 0;
const touched = [];
for (const root of roots) {
  for (const file of walk(root)) {
    const text = fs.readFileSync(file, "utf8");
    if (!text.includes(OLD)) continue;
    fs.writeFileSync(file, text.split(OLD).join(NEW), "utf8");
    fixed += 1;
    touched.push(path.relative(frontendRoot, file));
  }
}

console.log(
  fixed
    ? `Fixed AGP ProGuard defaults in ${fixed} file(s):\n  ${touched.join("\n  ")}`
    : "No proguard-android.txt defaults found (already OK).",
);
