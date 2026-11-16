// Run with `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { components } from "../src/api/schema";
import { greeting, isDone, nextBadge, nextItem, weekStrip } from "../src/features/dashboard/today";

type Dashboard = components["schemas"]["DashboardOut"];
type PlanItem = components["schemas"]["PlanItemOut"];

function item(id: string, done: boolean | null): PlanItem {
  return {
    id,
    kind: "review",
    title: id,
    why: "",
    minutes: 5,
    done,
    pattern_key: null,
    chapter_id: null,
    resource_id: null,
    task_id: null,
    class_task_id: null,
    url: null,
    words: [],
  };
}

/** Only the fields the badge rule reads. */
function board(streak: number, mastered: number, completed: number, studiedToday = false) {
  return {
    date: "2026-11-13",
    on_track: { streak, last_studied: studiedToday ? "2026-11-13" : "2026-11-12" },
    vocabulary: { mastered },
    chapters: { completed, total: 12 },
  } as unknown as Dashboard;
}

test("the greeting follows the time of day", () => {
  assert.equal(greeting(7), "Guten Morgen!");
  assert.equal(greeting(11), "Guten Tag!");
  assert.equal(greeting(17), "Guten Tag!");
  assert.equal(greeting(18), "Guten Abend!");
  assert.equal(greeting(2), "Guten Abend!"); // still the night before
});

test("Continue opens the first item that isn't done, counting the learner's own ticks", () => {
  const items = [item("review", true), item("listening", null), item("grammar", false)];
  assert.equal(nextItem(items, [])?.id, "listening");
  assert.equal(nextItem(items, ["listening"])?.id, "grammar");
  assert.equal(isDone(items[2], ["grammar"]), false); // ticks only count for untracked items
  assert.equal(nextItem([item("review", true)], []), null);
});

test("the week strip runs Monday to Sunday and marks the days studied", () => {
  // Friday the 13th of November 2026; studied Tuesday to Thursday.
  const week = weekStrip(["2026-11-10", "2026-11-11", "2026-11-12"], "2026-11-13");
  assert.deepEqual(
    week.map((d) => d.label),
    ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
  );
  assert.deepEqual(
    week.map((d) => d.done),
    [false, true, true, true, false, false, false],
  );
  assert.equal(week.findIndex((d) => d.today), 4);
  assert.deepEqual(
    week.map((d) => d.future),
    [false, false, false, false, false, true, true],
  );
  assert.equal(weekStrip([], "2026-11-16")[0].today, true); // a Monday
  assert.equal(weekStrip([], "2026-11-15")[6].today, true); // a Sunday
  // A plan saved before the server sent `week`: no studied days, no crash.
  assert.deepEqual(
    weekStrip(undefined, "2026-11-13").map((d) => d.done),
    [false, false, false, false, false, false, false],
  );
});

test("a streak milestone reached today is a new badge", () => {
  const badge = nextBadge(board(7, 0, 0, true));
  assert.equal(badge?.isNew, true);
  assert.equal(badge?.title, "7 days in a row");
  // The same streak, but today isn't studied yet: not new, the next goal is shown instead.
  assert.equal(nextBadge(board(7, 0, 0, false))?.isNew, false);
});

test("otherwise the badge row shows the goal the learner is closest to", () => {
  // Streak 5 of 7 (71%) beats 30 of 50 words (60%) and 2 of 3 chapters (67%).
  const badge = nextBadge(board(5, 30, 2));
  assert.deepEqual(badge, {
    title: "7 days in a row",
    progress: "5/7",
    detail: "2 more days to go",
    isNew: false,
  });
  assert.equal(nextBadge(board(0, 9, 0))?.detail, "1 more word to know well");
  assert.equal(nextBadge(board(0, 0, 0))?.title, "3 days in a row"); // all at zero: the first one
  assert.equal(nextBadge(board(400, 2000, 12)), null); // everything reached
});
