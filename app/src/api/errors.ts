export const OFFLINE_MESSAGE =
  "Can't reach the server. Check your internet connection. If the server was asleep, give it a minute and try again.";
export const TIMEOUT_MESSAGE =
  "The server is taking too long to answer. It may be waking up: try again in a minute.";

/** Why a request failed. `kind` tells "no answer" (offline, timeout) from "answered with an error". */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: "http" | "offline" | "timeout",
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Whether TanStack Query should try a failed read again. Worth retrying: no connection, a slow
 * server (the free server sleeps and takes up to a minute to wake) and server errors. Not worth
 * it: "not found", "invalid" or "not allowed" will be the same the second time.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  if (error.kind === "timeout") return failureCount < 1; // each try already waited a minute
  if (error.kind === "offline") return failureCount < 2;
  return failureCount < 2 && (error.status ?? 0) >= 500;
}

/**
 * Whether an answer waiting to be uploaded should be kept and tried again after this response.
 *
 * Only a refusal that will be the same next time lets go of it: the card is gone (404), the id
 * was used for another card (409) or the answer itself is invalid (422). Everything else is
 * about the moment, not the answer: the sign-in could not be refreshed (401, 403), the server
 * was slow or busy (408, 429) or had a problem (5xx). Dropping the answer then would lose the
 * learner's work for something that fixes itself.
 */
export function keepForRetry(status: number): boolean {
  return status === 401 || status === 403 || status === 408 || status === 429 || status >= 500;
}

type ApiResult<T> = { data?: T; error?: unknown; response: Response };

// Turns an openapi-fetch result into data, or throws an Error with the backend's message.
export function unwrap<T>({ data, error, response }: ApiResult<T>): T {
  if (error !== undefined || !response.ok) {
    throw new ApiError(
      describe(error) ?? fallbackMessage(response.status),
      "http",
      response.status,
    );
  }
  return data as T;
}

function fallbackMessage(status: number): string {
  if (status === 401) return "Your sign-in has expired. Sign out and sign in again.";
  if (status >= 500) return "The server had a problem. Please try again in a moment.";
  return `Request failed (${status})`;
}

function describe(error: unknown): string | undefined {
  if (error && typeof error === "object" && "detail" in error) {
    const { detail } = error as { detail: unknown };
    if (typeof detail === "string") return detail;
    // The AI layer sends { code, message }: the message is written to be shown to the learner.
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
    if (Array.isArray(detail)) {
      // FastAPI validation errors: [{ loc, msg }, ...]
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : String(d)))
        .join("\n");
    }
  }
  return undefined;
}
