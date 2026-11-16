import { ApiError } from "../../api/errors";

export type SendFailure = {
  /** The line shown under the unsent message. */
  message: string;
  /** Trying again with the same id may work (no connection, a slow or busy server). */
  retryable: boolean;
  /** The person has no display name on the server (yet): the name form must open. */
  needsName: boolean;
};

/**
 * What a failed send means. A send that got no answer, or a busy or broken server (408, 429, 5xx,
 * and a sign-in that could not be refreshed), is worth another try, and trying again with the same
 * id can never post twice. A refusal (the message it answers is gone, the text is not allowed)
 * will be the same next time, so the person is told and chooses what to do with it.
 */
export function classifySendError(error: unknown): SendFailure {
  if (error instanceof ApiError) {
    const status = error.status ?? 0;
    if (error.kind !== "http") return { message: error.message, retryable: true, needsName: false };
    if (status === 409) return { message: error.message, retryable: false, needsName: true };
    const retryable = status === 401 || status === 403 || status === 408 || status === 429 || status >= 500;
    return { message: error.message, retryable, needsName: false };
  }
  return { message: "Could not send the message.", retryable: true, needsName: false };
}
