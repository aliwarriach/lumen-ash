// Run with `npm test`. Day headings and name colours in the chat list.
import assert from "node:assert/strict";
import { test } from "node:test";

import { authorColor, dayLabel, toRows } from "../src/features/community/rows";
import type { ChatItem } from "../src/features/community/store";

function item(id: string, when: Date): ChatItem {
  return {
    id,
    status: "sent",
    authorId: "u",
    authorName: "U",
    body: id,
    deleted: false,
    reply: null,
    attachment: null,
    createdAt: when.toISOString(),
    error: null,
  };
}

const NOW = new Date(2026, 10, 12, 15, 0);

test("rows are newest first, with a heading after (above) the oldest message of each day", () => {
  const rows = toRows(
    [
      item("a", new Date(2026, 10, 11, 9, 0)),
      item("b", new Date(2026, 10, 11, 9, 5)),
      item("c", new Date(2026, 10, 12, 8, 0)),
    ],
    NOW,
    "en-GB",
  );
  assert.deepEqual(
    rows.map((r) => (r.kind === "day" ? `day:${r.label}` : r.item.id)),
    ["c", "day:Today", "b", "a", "day:Yesterday"],
  );
});

test("no messages, no rows", () => {
  assert.deepEqual(toRows([], NOW), []);
});

test("day labels", () => {
  assert.equal(dayLabel(new Date(2026, 10, 12, 1, 0), NOW, "en-GB"), "Today");
  assert.equal(dayLabel(new Date(2026, 10, 11, 23, 59), NOW, "en-GB"), "Yesterday");
  assert.match(dayLabel(new Date(2026, 10, 5, 12, 0), NOW, "en-GB"), /Thu.*5.*Nov/);
  assert.match(dayLabel(new Date(2025, 11, 30, 12, 0), NOW, "en-GB"), /2025/);
});

test("a name colour is steady per person and always one of the palette", () => {
  const names = ["#111111", "#222222", "#333333"];
  const a = authorColor("3f2b1c6e-0000-4000-8000-000000000001", names);
  assert.equal(a, authorColor("3f2b1c6e-0000-4000-8000-000000000001", names));
  assert.ok(names.includes(a));
});
