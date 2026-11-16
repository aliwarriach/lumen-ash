import assert from "node:assert/strict";
import { test } from "node:test";

import { looksLikeEmail, passwordProblem } from "../src/features/auth/password";

test("a new password needs 8 characters and must be typed twice the same", () => {
  assert.equal(passwordProblem("longenough", "longenough"), null);
  assert.notEqual(passwordProblem("short", "short"), null);
  assert.notEqual(passwordProblem("longenough", "different1"), null);
});

test("looksLikeEmail catches obvious typos only", () => {
  assert.equal(looksLikeEmail(" a@b.co "), true);
  for (const bad of ["", "a", "a@b", "a b@c.de", "@b.co"]) assert.equal(looksLikeEmail(bad), false, bad);
});
