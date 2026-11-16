import assert from "node:assert/strict";
import { test } from "node:test";

import { usernameProblem } from "../src/features/community/username";

test("accepts ordinary usernames, with German letters and underscores", () => {
  for (const ok of ["Ali", "sara_k", "Müller", "Max_99", "  Ali  ", "a".repeat(20)]) {
    assert.equal(usernameProblem(ok), null, ok);
  }
});

test("refuses too short, too long, spaces, symbols and no letters", () => {
  for (const bad of ["", "Al", "a".repeat(21), "Ali Khan", "Ali.K", "Ali!", "___", "123", "Аli"]) {
    assert.notEqual(usernameProblem(bad), null, bad);
  }
});
