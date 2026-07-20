/**
 * Open the Capacitor Android project in the correct Android Studio install.
 *
 * Capacitor defaults to:
 *   C:\Program Files\Android\Android Studio\bin\studio64.exe
 * and skips the Windows registry if that path exists. Prefer the registry
 * Path (or CAPACITOR_ANDROID_STUDIO_PATH) when multiple installs exist.
 *
 * Usage: node scripts/open-android-studio.mjs
 */
import { existsSync } from "node:fs";
import { spawn, execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const DEFAULT_STUDIO =
  "C:\\Program Files\\Android\\Android Studio\\bin\\studio64.exe";
const ANDROID_DIR = resolve(ROOT, "android");

function registryStudioHome() {
  try {
    const out = execFileSync(
      "reg",
      ["QUERY", "HKLM\\SOFTWARE\\Android Studio", "/v", "Path"],
      { encoding: "utf8" },
    );
    const m = out.match(/Path\s+REG_SZ\s+(.+)/i);
    return m ? m[1].trim() : null;
  } catch {
    return null;
  }
}

function resolveStudioExe() {
  if (process.env.CAPACITOR_ANDROID_STUDIO_PATH) {
    return {
      source: "env",
      path: process.env.CAPACITOR_ANDROID_STUDIO_PATH,
    };
  }
  const home = registryStudioHome();
  if (home) {
    const exe = resolve(home, "bin", "studio64.exe");
    if (existsSync(exe)) {
      return { source: "registry", path: exe, home };
    }
  }
  if (existsSync(DEFAULT_STUDIO)) {
    return { source: "capacitor-default", path: DEFAULT_STUDIO };
  }
  return { source: "missing", path: null };
}

const resolved = resolveStudioExe();

if (!resolved.path || !existsSync(resolved.path)) {
  console.error(
    "Android Studio not found. Install it or set CAPACITOR_ANDROID_STUDIO_PATH.",
  );
  process.exit(1);
}

if (!existsSync(ANDROID_DIR)) {
  console.error(
    `Android project missing at ${ANDROID_DIR}. Run: npx cap add android`,
  );
  process.exit(1);
}

console.log(`Opening Android project with (${resolved.source}):`);
console.log(`  ${resolved.path}`);
console.log(`  project: ${ANDROID_DIR}`);

const child = spawn(resolved.path, [ANDROID_DIR], {
  detached: true,
  stdio: "ignore",
  windowsHide: false,
});

child.on("error", (err) => {
  console.error(err.message);
  process.exit(1);
});

child.unref();
console.log(
  "Launch requested. If a 'Cannot start the IDE' dialog appears, the chosen install is corrupt — reinstall Android Studio or point CAPACITOR_ANDROID_STUDIO_PATH at a working studio64.exe.",
);
