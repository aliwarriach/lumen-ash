// Run with `npm test`. The chat's merge rules: what shows, in what order, and when the cursor moves.
import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiError } from "../src/api/errors";
import { classifySendError } from "../src/features/community/sendError";
import {
  addPending,
  applyChanges,
  applyEvent,
  applyLatest,
  applyOlder,
  initialState,
  markFailed,
  removePending,
  retry,
  visible,
  type ChatState,
  type CommunityMessage,
} from "../src/features/community/store";

const ME = { id: "u-me", name: "Me" };

function msg(seq: number, over: Partial<CommunityMessage> = {}): CommunityMessage {
  return {
    id: `m${seq}`,
    seq,
    rev: seq,
    author_id: "u-other",
    author_name: "Other",
    body: `text ${seq}`,
    deleted: false,
    reply_to: null,
    attachment: null,
    created_at: new Date(2026, 10, 12, 10, seq).toISOString(),
    ...over,
  };
}

function loaded(...items: CommunityMessage[]): ChatState {
  const rev = Math.max(0, ...items.map((m) => m.rev));
  return applyLatest(initialState, { items, has_more: false, rev });
}

const ids = (s: ChatState) => visible(s).map((i) => i.id);

test("the first page sets the list and the cursor", () => {
  const s = applyLatest(initialState, { items: [msg(5), msg(6)], has_more: true, rev: 6 });
  assert.deepEqual(ids(s), ["m5", "m6"]);
  assert.equal(s.cursor, 6);
  assert.equal(s.oldestSeq, 5);
  assert.equal(s.hasOlder, true);
});

test("messages are shown by seq whatever order they arrived in", () => {
  let s = loaded(msg(1));
  s = applyEvent(s, msg(3));
  s = applyEvent(s, msg(2));
  assert.deepEqual(ids(s), ["m1", "m2", "m3"]);
});

test("a pushed message never moves the cursor: only the changes request does", () => {
  let s = loaded(msg(1));
  s = applyEvent(s, msg(2));
  assert.equal(s.cursor, 1, "the socket must not advance what 'changes' asks after");
  s = applyChanges(s, { items: [msg(2)], rev: 2, has_more: false });
  assert.equal(s.cursor, 2);
});

test("the cursor never goes backwards", () => {
  let s = loaded(msg(1), msg(2));
  s = applyChanges(s, { items: [], rev: 1, has_more: false });
  assert.equal(s.cursor, 2);
});

test("the same message arriving twice shows once", () => {
  let s = loaded(msg(1));
  s = applyEvent(s, msg(2));
  s = applyChanges(s, { items: [msg(2)], rev: 2, has_more: false });
  assert.deepEqual(ids(s), ["m1", "m2"]);
});

test("the copy with the higher rev wins, in either order", () => {
  const deleted = msg(2, { rev: 9, deleted: true, body: null });
  let s = loaded(msg(1), msg(2));
  s = applyEvent(s, deleted);
  assert.equal(visible(s)[1].deleted, true);
  // The older copy arrives late (a sync that started before the delete): it must not bring the text back.
  s = applyChanges(s, { items: [msg(2)], rev: 2, has_more: false });
  assert.equal(visible(s)[1].deleted, true);
  assert.equal(visible(s)[1].body, null);
});

test("a deletion is applied to the message already on screen", () => {
  let s = loaded(msg(1), msg(2));
  s = applyChanges(s, {
    items: [msg(1, { rev: 5, deleted: true, body: null })],
    rev: 5,
    has_more: false,
  });
  assert.equal(visible(s)[0].deleted, true);
  assert.equal(visible(s)[0].body, null);
});

test("a change to a message far up the history that is not loaded is ignored", () => {
  let s = loaded(msg(50), msg(51));
  s = applyChanges(s, { items: [msg(3, { rev: 80, deleted: true, body: null })], rev: 80, has_more: false });
  assert.deepEqual(ids(s), ["m50", "m51"]);
  assert.equal(s.cursor, 80, "the cursor still moves: the change was seen");
});

test("pushes before the first page are ignored; the page and 'changes' bring them", () => {
  const s = applyEvent(initialState, msg(1));
  assert.deepEqual(ids(s), []);
  assert.equal(s.cursor, null);
});

test("an empty room accepts its first messages", () => {
  let s = loaded();
  assert.equal(s.cursor, 0);
  s = applyEvent(s, msg(1));
  s = applyEvent(s, msg(2));
  assert.deepEqual(ids(s), ["m1", "m2"]);
});

test("older pages are added in front and leave the cursor alone", () => {
  let s = applyLatest(initialState, { items: [msg(5), msg(6)], has_more: true, rev: 6 });
  s = applyOlder(s, { items: [msg(3), msg(4)], has_more: false, rev: 6 });
  assert.deepEqual(ids(s), ["m3", "m4", "m5", "m6"]);
  assert.equal(s.cursor, 6);
  assert.equal(s.oldestSeq, 3);
  assert.equal(s.hasOlder, false);
});

test("starting again from the latest page replaces what was there", () => {
  let s = loaded(msg(1), msg(2));
  s = applyLatest(s, { items: [msg(90), msg(91)], has_more: true, rev: 91 });
  assert.deepEqual(ids(s), ["m90", "m91"]);
  assert.equal(s.cursor, 91);
});

// --- sending -------------------------------------------------------------------------------

const send = (s: ChatState, id: string, now: number, replyToId?: string) =>
  addPending(s, { id, body: `body ${id}`, author: ME, replyToId, now });

test("a sent message shows at once, after the confirmed ones, marked as sending", () => {
  const s = send(loaded(msg(1), msg(2)), "p1", 1000);
  const items = visible(s);
  assert.deepEqual(items.map((i) => i.id), ["m1", "m2", "p1"]);
  assert.equal(items[2].status, "sending");
  assert.equal(items[2].authorName, "Me");
});

test("unsent messages keep the order they were written in", () => {
  let s = loaded(msg(1));
  s = send(s, "b", 2000);
  s = send(s, "a", 1000);
  assert.deepEqual(ids(s), ["m1", "a", "b"]);
});

test("the pending copy disappears when the confirmed one arrives, by socket or by answer", () => {
  let s = send(loaded(msg(1)), "p1", 1000);
  // the socket echo arrives before the POST answers
  s = applyEvent(s, msg(2, { id: "p1", author_id: ME.id, author_name: ME.name, body: "body p1" }));
  assert.deepEqual(ids(s), ["m1", "p1"]);
  assert.equal(s.pending.length, 0);
  assert.equal(visible(s)[1].status, "sent");
});

test("the pending copy also goes when only the 'changes' request brings the message", () => {
  let s = send(loaded(msg(1)), "p1", 1000);
  s = applyChanges(s, {
    items: [msg(2, { id: "p1", rev: 2 })],
    rev: 2,
    has_more: false,
  });
  assert.equal(s.pending.length, 0);
  assert.deepEqual(ids(s), ["m1", "p1"]);
});

test("adding a send whose id is already confirmed does nothing", () => {
  const s = loaded(msg(1, { id: "p1" }));
  assert.equal(send(s, "p1", 1000), s);
});

test("a failed send stays with its reason, and retrying keeps the same id", () => {
  let s = send(loaded(msg(1)), "p1", 1000);
  s = markFailed(s, "p1", "Can't reach the server.");
  assert.equal(visible(s)[1].status, "failed");
  assert.equal(visible(s)[1].error, "Can't reach the server.");
  s = retry(s, "p1");
  assert.equal(visible(s)[1].status, "sending");
  assert.equal(visible(s)[1].error, null);
  assert.deepEqual(ids(s), ["m1", "p1"]);
});

test("a send can be given up", () => {
  let s = send(loaded(msg(1)), "p1", 1000);
  s = removePending(s, "p1");
  assert.deepEqual(ids(s), ["m1"]);
});

test("unsent messages survive starting again from the latest page", () => {
  let s = send(loaded(msg(1)), "p1", 1000);
  s = applyLatest(s, { items: [msg(40)], has_more: true, rev: 40 });
  assert.deepEqual(ids(s), ["m40", "p1"]);
});

// --- replies ---------------------------------------------------------------------------------

const replyTo = { id: "m1", author_name: "Other", excerpt: "text 1" };

test("a reply quotes the local copy of its target, so a deleted target shows as deleted", () => {
  let s = loaded(msg(1), msg(2, { reply_to: replyTo }));
  assert.equal(visible(s)[1].reply?.excerpt, "text 1");
  s = applyEvent(s, msg(1, { rev: 7, deleted: true, body: null }));
  assert.equal(visible(s)[1].reply?.excerpt, null);
});

test("a reply to a message that is not loaded falls back to what the server sent", () => {
  const s = loaded(msg(60, { reply_to: { id: "m3", author_name: "Someone", excerpt: "far above" } }));
  assert.deepEqual(visible(s)[0].reply, { id: "m3", authorName: "Someone", excerpt: "far above" });
});

test("my own reply quotes the message I answered while it is still unsent", () => {
  const s = send(loaded(msg(1)), "p1", 1000, "m1");
  assert.equal(visible(s)[1].reply?.authorName, "Other");
  assert.equal(visible(s)[1].reply?.excerpt, "text 1");
  assert.equal(s.pending[0].replyToId, "m1");
});

// --- what a failed send means --------------------------------------------------------------------

test("no connection and a slow server are worth another try", () => {
  assert.equal(classifySendError(new ApiError("offline", "offline")).retryable, true);
  assert.equal(classifySendError(new ApiError("slow", "timeout")).retryable, true);
});

test("too fast (429), busy or broken servers are worth another try", () => {
  for (const status of [401, 403, 408, 429, 500, 503]) {
    assert.equal(classifySendError(new ApiError("x", "http", status)).retryable, true, String(status));
  }
});

test("a refusal will be the same next time", () => {
  for (const status of [404, 422]) {
    const f = classifySendError(new ApiError("That message is gone", "http", status));
    assert.equal(f.retryable, false, String(status));
    assert.equal(f.message, "That message is gone");
  }
});

test("409 means the server has no name for this person yet", () => {
  const f = classifySendError(new ApiError("Choose a name first", "http", 409));
  assert.equal(f.needsName, true);
  assert.equal(f.retryable, false);
});
