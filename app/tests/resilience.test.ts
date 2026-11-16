// Run with `npm test`. Covers the code that decides what happens when the network misbehaves.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ApiError,
  OFFLINE_MESSAGE,
  TIMEOUT_MESSAGE,
  keepForRetry,
  shouldRetry,
  unwrap,
} from "../src/api/errors";
import { apiFetch } from "../src/api/fetch";

const request = new Request("https://example.test/health");

test("a request that gets an answer passes straight through", async () => {
  const ok = new Response("{}", { status: 200 });
  assert.equal(await apiFetch(request, 1000, async () => ok), ok);
});

test("no connection becomes a message that says what to do", async () => {
  const failing = async () => {
    throw new TypeError("Network request failed");
  };
  await assert.rejects(apiFetch(request, 1000, failing), (e: unknown) => {
    assert.ok(e instanceof ApiError);
    assert.equal(e.kind, "offline");
    assert.equal(e.message, OFFLINE_MESSAGE);
    return true;
  });
});

test("a server that never answers is given up on, with a message about waking up", async () => {
  const hanging = (_input: RequestInfo | URL, init?: RequestInit) =>
    new Promise<Response>((_, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new Error("aborted")));
    });
  await assert.rejects(apiFetch(request, 30, hanging as typeof fetch), (e: unknown) => {
    assert.ok(e instanceof ApiError);
    assert.equal(e.kind, "timeout");
    assert.equal(e.message, TIMEOUT_MESSAGE);
    return true;
  });
});

test("reads are retried when the server is unreachable, slow or broken, but not when we are wrong", () => {
  const offline = new ApiError("x", "offline");
  const timeout = new ApiError("x", "timeout");
  const http = (status: number) => new ApiError("x", "http", status);

  assert.equal(shouldRetry(0, offline), true);
  assert.equal(shouldRetry(1, offline), true);
  assert.equal(shouldRetry(2, offline), false); // gives up after two retries
  assert.equal(shouldRetry(0, timeout), true);
  assert.equal(shouldRetry(1, timeout), false); // each timeout already cost a minute
  assert.equal(shouldRetry(0, http(503)), true);
  assert.equal(shouldRetry(0, http(500)), true);
  for (const status of [400, 401, 404, 422, 429]) {
    assert.equal(shouldRetry(0, http(status)), false, `HTTP ${status}`);
  }
  assert.equal(shouldRetry(0, new Error("a bug")), false);
});

test("unwrap keeps the backend's own message, and explains status codes that have none", () => {
  const response = (status: number) => ({ status, ok: false }) as Response;
  const message = (error: unknown, status: number) => {
    try {
      unwrap({ error, response: response(status) });
    } catch (e) {
      return (e as ApiError).message;
    }
    return "";
  };
  assert.equal(message({ detail: "Word not found" }, 404), "Word not found");
  assert.equal(message({ detail: { code: "x", message: "No AI left today" } }, 429), "No AI left today");
  assert.match(message({}, 500), /server had a problem/);
  assert.match(message({}, 401), /sign-in has expired/);
  assert.equal(message({}, 418), "Request failed (418)");
});

test("an answer waiting to upload is only let go when the server refuses it for good", () => {
  // The card was deleted, the id belongs to another card, the answer is invalid: never different.
  for (const status of [404, 409, 422]) assert.equal(keepForRetry(status), false, String(status));
  // A sign-in that could not be refreshed, a busy or waking server, a server fault: try later.
  for (const status of [401, 403, 408, 429, 500, 502, 503]) {
    assert.equal(keepForRetry(status), true, String(status));
  }
});
