/** Shared frontend utilities (API client, auth helpers). */
export { getApiBaseUrl as API_BASE_URL_FN, getApiBaseUrl } from "@/lib/apiBase";

/** @deprecated Prefer getApiBaseUrl() — this is only the build-time default. */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
