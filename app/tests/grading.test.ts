// Run with `npm test`. The instant, offline answer check. It must agree with the server's
// (backend/app/review/grading.py, tested in backend/tests/test_review_umlauts.py and
// test_review_rules.py): the same cases are used on both sides.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { components } from "../src/api/schema";
import {
  UMLAUT_TIP,
  checkArticle,
  checkCorrection,
  checkProduce,
  onlyUmlautsDiffer,
} from "../src/features/review/grading";

type Word = components["schemas"]["QueueWord"];

function noun(german: string, article: "der" | "die" | "das", plural: string): Word {
  return { kind: "noun", german, article, plural, plural_only: false } as Word;
}

const MAEDCHEN = noun("Mädchen", "das", "Mädchen");
const STRASSE = noun("Straße", "die", "Straßen");
const MUTTER = noun("Mutter", "die", "Mütter");

test("an umlaut slip is told apart from any other mistake", () => {
  const cases: [string, string, boolean][] = [
    ["das Madchen", "das Mädchen", true],
    ["das Maedchen", "das Mädchen", true],
    ["die Strasse", "die Straße", true],
    ["Mutter", "Mütter", true],
    ["Fussball", "Fußball", true],
    ["schoen", "schön", true],
    ["das Mädchen", "das Mädchen", false],
    ["das Madchin", "das Mädchen", false],
    ["der Tisch", "der Tisch", false],
    ["der Tüsch", "der Tisch", false],
  ];
  for (const [given, expected, only] of cases) {
    assert.equal(onlyUmlautsDiffer(given, expected), only, `${given} / ${expected}`);
  }
});

test("a missing umlaut is still wrong but says exactly what to check", () => {
  for (const answer of ["das Madchen", "das Maedchen"]) {
    assert.deepEqual(checkProduce(MAEDCHEN, answer), {
      correct: false,
      expected: "das Mädchen",
      feedback: UMLAUT_TIP,
    });
  }
  assert.equal(checkProduce(STRASSE, "die Strasse").feedback, UMLAUT_TIP);
  assert.equal(checkProduce(MAEDCHEN, "das Mädchen").correct, true);
  assert.match(checkProduce(MAEDCHEN, "das mädchen").feedback ?? "", /capital/);
  assert.equal(checkProduce(MAEDCHEN, "der Mädchen").feedback, "Wrong article: it's das Mädchen.");
});

test("a plural that only lacks its umlaut gets the tip too", () => {
  assert.equal(checkArticle(MUTTER, "die", "Mutter").feedback, `The plural is die Mütter. ${UMLAUT_TIP}`);
  assert.equal(checkArticle(MUTTER, "die", "Muttern").feedback, "The plural is die Mütter.");
  assert.equal(checkArticle(MUTTER, "die", "Mütter").correct, true);
});

test("a retried mistake gets the tip", () => {
  assert.equal(checkCorrection("Ich heiße Ali.", "Ich heisse Ali.").feedback, UMLAUT_TIP);
  assert.equal(checkCorrection("Ich heiße Ali.", "Ich heiße Ali").correct, true);
});

test("the same letters in another Unicode form are the same answer", () => {
  const decomposed = "Mädchen".normalize("NFD");
  assert.notEqual(decomposed, "Mädchen");
  const stored = noun(decomposed, "das", "Mütter".normalize("NFD"));
  assert.equal(checkProduce(stored, "das Mädchen").correct, true);
  assert.equal(checkProduce(MAEDCHEN, `das ${decomposed}`).correct, true);
  assert.equal(checkArticle(stored, "das", "Mütter").correct, true);
});
