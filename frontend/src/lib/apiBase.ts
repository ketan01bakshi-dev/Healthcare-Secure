/** Runtime clinic API base URL — override build-time env without rebuilding the APK. */

const STORAGE_KEY = "healthcare_api_base_url";

const BUILD_DEFAULT =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Share / production APKs bake the cloud API URL — do not allow localStorage override
 * so a forwarded APK cannot be pointed at a rogue server from the UI.
 */
export function isProductionApiLocked(): boolean {
  if (process.env.NEXT_PUBLIC_LOCK_API_BASE === "true") return true;
  const d = (BUILD_DEFAULT || "").toLowerCase();
  return d.includes("aarogyaoneconnect.in");
}

/** Host looks like a public domain (not LAN IP / localhost) → default https. */
export function looksLikePublicHostname(host: string): boolean {
  const h = host.trim().toLowerCase();
  if (!h || h === "localhost" || h.endsWith(".local")) return false;
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(h)) return false;
  if (h.includes(":")) return false;
  return h.includes(".");
}

export function normalizeApiBaseUrl(raw: string): string {
  let url = (raw || "").trim().replace(/\/+$/, "");
  if (!url) return BUILD_DEFAULT;
  if (!/^https?:\/\//i.test(url)) {
    const hostPart = url.split("/")[0] ?? url;
    const hostname = hostPart.split(":")[0] ?? hostPart;
    const scheme = looksLikePublicHostname(hostname) ? "https" : "http";
    url = `${scheme}://${url}`;
  }
  return url.replace(/\/+$/, "");
}

export function getApiBaseUrl(): string {
  if (typeof window === "undefined") return BUILD_DEFAULT;
  if (isProductionApiLocked()) {
    return normalizeApiBaseUrl(BUILD_DEFAULT);
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored?.trim()) return normalizeApiBaseUrl(stored);
  } catch {
    /* private mode */
  }
  return BUILD_DEFAULT;
}

export function setApiBaseUrl(url: string): void {
  if (typeof window === "undefined") return;
  if (isProductionApiLocked()) return;
  const normalized = normalizeApiBaseUrl(url);
  try {
    localStorage.setItem(STORAGE_KEY, normalized);
  } catch {
    /* ignore */
  }
}

export function getDefaultApiBaseUrl(): string {
  return BUILD_DEFAULT;
}

/** True when the URL would hit the phone itself (useless on a real device). */
export function isLoopbackApiBaseUrl(url: string): boolean {
  try {
    const u = new URL(normalizeApiBaseUrl(url));
    const host = u.hostname.toLowerCase();
    return (
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "0.0.0.0" ||
      host === "::1" ||
      host === "[::1]"
    );
  } catch {
    return true;
  }
}

/**
 * Capacitor / Android WebView is not a desktop browser — localhost means the phone.
 * Require an explicit LAN or cloud URL before calling the API.
 */
export function needsClinicUrlSetup(): boolean {
  if (typeof window === "undefined") return false;
  if (isProductionApiLocked()) return false;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored?.trim() && !isLoopbackApiBaseUrl(stored)) return false;
  } catch {
    /* ignore */
  }
  const ua = navigator.userAgent || "";
  const likelyDevice =
    /Android|iPhone|iPad|Capacitor/i.test(ua) ||
    !!(window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } })
      .Capacitor?.isNativePlatform?.();
  if (!likelyDevice) return false;
  return isLoopbackApiBaseUrl(getApiBaseUrl());
}

/** True in Capacitor Android/iOS shell (not mobile browser). */
export function isNativeApp(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return !!(
      window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } }
    ).Capacitor?.isNativePlatform?.();
  } catch {
    return false;
  }
}
