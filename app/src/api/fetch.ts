import { ApiError, OFFLINE_MESSAGE, TIMEOUT_MESSAGE } from "@/api/errors";

// The free server goes to sleep and can take about a minute to wake, so wait that long, but not
// forever: without a limit a dead connection leaves a spinner on screen until the app is closed.
export const REQUEST_TIMEOUT_MS = 60_000;

/** `fetch` with a time limit, and failures turned into messages a learner can act on. */
export async function apiFetch(
  request: Request,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
  doFetch: typeof fetch = fetch,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await doFetch(request, { signal: controller.signal });
  } catch {
    throw controller.signal.aborted
      ? new ApiError(TIMEOUT_MESSAGE, "timeout")
      : new ApiError(OFFLINE_MESSAGE, "offline");
  } finally {
    clearTimeout(timer);
  }
}
