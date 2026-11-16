// Run with `npm test`. Word banks and guided writing; the same cases as
// backend/tests/test_sentences.py, so the phone and the server agree.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  blankProblem,
  fillFrame,
  isCorrect,
  scrambleTiles,
  shownAnswer,
  type Blank,
  type PracticeItem,
} from "../src/features/practice/check";

function item(over: Partial<PracticeItem>): PracticeItem {
  return {
    id: "x",
    kind: "bank",
    prompt: "I live in Berlin.",
    english: null,
    options: [],
    tiles: ["Ich", "wohne", "in", "Berlin", "wohnst", "aus"],
    distractors: ["wohnst", "aus"],
    answers: ["Ich wohne in Berlin", "In Berlin wohne ich"],
    exact_case: false,
    end: ".",
    hint: "h",
    why: "w",
    ...over,
  };
}

const blank = (over: Partial<Blank>): Blank => ({
  label: "your name",
  example: "Ali",
  rule: "any",
  accepted: [],
  ends_with: null,
  ...over,
});

test("a word bank is right without the extra tiles, and wrong with one", () => {
  const bank = item({});
  assert.equal(isCorrect(bank, "Ich wohne in Berlin"), true);
  assert.equal(isCorrect(bank, "in Berlin wohne Ich"), true);
  assert.equal(isCorrect(bank, "Ich wohnst in Berlin"), false);
  assert.equal(isCorrect(bank, "Ich wohne in Berlin aus"), false);
  assert.equal(shownAnswer(bank), "Ich wohne in Berlin.");
});

test("scrambling a word bank keeps every tile, extras included", () => {
  const bank = item({});
  assert.deepEqual(scrambleTiles(bank).sort(), [...bank.tiles].sort());
});

test("guided-writing gaps follow simple rules", () => {
  const name = blank({ rule: "capital" });
  assert.equal(blankProblem(name, "Sara"), null);
  assert.match(blankProblem(name, "sara") ?? "", /capital/);
  assert.match(blankProblem(name, "  ") ?? "", /Fill in/);

  const verb = blank({ label: "a verb in the ich-form", rule: "lower", ends_with: "e" });
  assert.equal(blankProblem(verb, "lese"), null);
  assert.match(blankProblem(verb, "lesen") ?? "", /-e/);
  assert.match(blankProblem(verb, "Lese") ?? "", /small letter/);

  const month = blank({ label: "a month", rule: "capital", accepted: ["Mai", "März"] });
  assert.equal(blankProblem(month, "März"), null);
  assert.match(blankProblem(month, "Montag") ?? "", /isn't one of/);

  const time = blank({ label: "a time" }); // digits are fine where any text is
  assert.equal(blankProblem(time, "7"), null);
});

test("the frame shows the learner's words in place, and gaps not yet filled", () => {
  const frame = "Ich heiße ___. Ich komme aus ___.";
  assert.equal(fillFrame(frame, ["Sara", " Pakistan "]), "Ich heiße Sara. Ich komme aus Pakistan.");
  assert.equal(fillFrame(frame, ["Sara", ""]), "Ich heiße Sara. Ich komme aus ___.");
});

test("a frame's model answer is what is shown after it", () => {
  const frame = item({ kind: "frame", tiles: [], distractors: [], answers: ["Ich heiße Ali."] });
  assert.equal(shownAnswer(frame), "Ich heiße Ali.");
});
