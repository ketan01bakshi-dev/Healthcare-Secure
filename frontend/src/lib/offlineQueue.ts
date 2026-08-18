/** Offline queue for vitals / lab results when the clinic API is unreachable. */

import { getApiBaseUrl } from "@/lib/apiBase";
import { authHeaders } from "@/lib/doctorSession";

const KEY = "healthcare_offline_queue";

export type OfflineJob = {
  id: string;
  path: string;
  body: unknown;
  createdAt: number;
};

function readQueue(): OfflineJob[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as OfflineJob[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeQueue(jobs: OfflineJob[]) {
  localStorage.setItem(KEY, JSON.stringify(jobs.slice(0, 50)));
}

export function enqueueOffline(
  path: string,
  body: unknown,
): OfflineJob {
  const job: OfflineJob = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    path,
    body,
    createdAt: Date.now(),
  };
  const q = readQueue();
  q.push(job);
  writeQueue(q);
  return job;
}

export function pendingOfflineCount(): number {
  return readQueue().length;
}

/** Drop jobs the server will never accept (validation / bad request). */
function isPermanentSyncFailure(status: number): boolean {
  return status === 400 || status === 422;
}

export async function flushOfflineQueue(): Promise<{
  sent: number;
  remaining: number;
  dropped: number;
}> {
  const q = readQueue();
  if (!q.length) return { sent: 0, remaining: 0, dropped: 0 };
  const remaining: OfflineJob[] = [];
  let sent = 0;
  let dropped = 0;
  for (const job of q) {
    try {
      const res = await fetch(`${getApiBaseUrl()}${job.path}`, {
        method: "POST",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(job.body),
      });
      if (res.ok) {
        sent += 1;
      } else if (isPermanentSyncFailure(res.status)) {
        dropped += 1;
      } else {
        remaining.push(job);
      }
    } catch {
      remaining.push(job);
    }
  }
  writeQueue(remaining);
  return { sent, remaining: remaining.length, dropped };
}
