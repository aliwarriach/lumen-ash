// Answers are saved on the phone first, then uploaded in order. Each carries its own id, so an
// upload that is retried after a dropped connection is recognised by the server, never doubled.
import AsyncStorage from "@react-native-async-storage/async-storage";

import { api } from "@/api/client";
import { keepForRetry } from "@/api/errors";
import type { components } from "@/api/schema";
import { deviceTimezone } from "@/lib/timezone";

export type ReviewIn = components["schemas"]["ReviewIn"];
export type ReviewOut = components["schemas"]["ReviewOut"];

const KEY = "review-outbox:v1";

type Listener = (pending: number) => void;
const listeners = new Set<Listener>();

async function load(): Promise<ReviewIn[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ReviewIn[]) : [];
  } catch {
    return [];
  }
}

async function save(items: ReviewIn[]): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(items));
  listeners.forEach((l) => l(items.length));
}

export async function pendingCount(): Promise<number> {
  return (await load()).length;
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function enqueue(review: ReviewIn): Promise<void> {
  await save([...(await load()), review]);
}

export async function clearOutbox(): Promise<void> {
  await AsyncStorage.removeItem(KEY);
  listeners.forEach((l) => l(0));
}

export type FlushResult = {
  sent: ReviewOut[];
  /** Answers the server refused for good (e.g. the word was deleted). Dropped, not retried. */
  rejected: { review: ReviewIn; message: string }[];
  /** True if uploading stopped early: no connection, a busy server or a sign-in to renew. */
  offline: boolean;
};

let inFlight: Promise<FlushResult> | null = null;

/** Uploads saved answers in order. Safe to call often; concurrent calls share one upload. */
export function flushOutbox(): Promise<FlushResult> {
  inFlight ??= doFlush().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function doFlush(): Promise<FlushResult> {
  const result: FlushResult = { sent: [], rejected: [], offline: false };
  let items = await load();
  while (items.length > 0) {
    const [next, ...rest] = items;
    let response: Response;
    let data: ReviewOut | undefined;
    let error: unknown;
    try {
      ({ data, error, response } = await api.POST("/reviews", {
        body: next,
        params: { query: { tz: deviceTimezone() } },
      }));
    } catch {
      result.offline = true; // no connection: keep everything for later
      break;
    }
    if (!response.ok && keepForRetry(response.status)) {
      result.offline = true; // waking up, busy, or the sign-in needs renewing: try again later
      break;
    }
    if (data) {
      result.sent.push(data);
    } else {
      result.rejected.push({ review: next, message: describe(error, response.status) });
    }
    items = rest;
    await save(items);
  }
  return result;
}

function describe(error: unknown, status: number): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `Rejected (${status})`;
}
