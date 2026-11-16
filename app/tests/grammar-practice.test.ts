// Run with `npm test`. The same cases as backend/tests/test_grammar_practice.py, so the instant
// check on the phone and the stored check on the server agree.
import assert from "node:assert/strict";
import { test } from "node:test";

import { filled, isCorrect, nearMiss, scrambleTiles, shuffle, type Exercise } from "../src/features/grammar/practice";

function ex(over: Partial<Exercise>): Exercise {
  return {
    id: "x",
    kind: "fill",
    prompt: "Ich ___ aus Pakistan. (kommen)",
    english: null,
    options: [],
    tiles: [],
    answers: ["komme"],
    exact_case: false,
    end: ".",
    hint: "h",
    why: "w",
    ...over,
  };
}

test("typed answers ignore spaces, the full stop and (usually) capitals", () => {
  const fill = ex({});
  assert.equal(isCorrect(fill, "komme"), true);
  assert.equal(isCorrect(fill, "  Komme. "), true);
  assert.equal(isCorrect(fill, "kommen"), false);
  assert.equal(isCorrect(fill, ""), false);
});

test("when the capital is the point, it must match", () => {
  const noun = ex({ prompt: "Ich trinke gern ___. (milk)", answers: ["Milch"], exact_case: true });
  assert.equal(isCorrect(noun, "Milch"), true);
  assert.equal(isCorrect(noun, "milch"), false);
  assert.match(nearMiss(noun, "milch") ?? "", /capital/);
});

test("choices must match exactly, capitals included", () => {
  const choice = ex({
    kind: "choice",
    options: ["Ich habe einen hund.", "Ich habe einen Hund."],
    answers: ["Ich habe einen Hund."],
  });
  assert.equal(isCorrect(choice, "Ich habe einen Hund."), true);
  assert.equal(isCorrect(choice, "Ich habe einen hund."), false);
});

test("a missing umlaut is wrong, with a tip that says so", () => {
  const plural = ex({ prompt: "ein Apfel, zwei ___", answers: ["Äpfel"], exact_case: true });
  assert.equal(isCorrect(plural, "Apfel"), false);
  assert.match(nearMiss(plural, "Apfel") ?? "", /ä, ö, ü/);
  assert.equal(nearMiss(plural, "Äpfel"), null);
});

test("word order accepts every listed order, whatever the tiles' capitals", () => {
  const order = ex({
    kind: "order",
    prompt: "Today I'm learning German.",
    tiles: ["Heute", "lerne", "ich", "Deutsch"],
    answers: ["Heute lerne ich Deutsch", "Ich lerne heute Deutsch"],
  });
  assert.equal(isCorrect(order, "Heute lerne ich Deutsch"), true);
  assert.equal(isCorrect(order, "ich lerne Heute Deutsch"), true);
  assert.equal(isCorrect(order, "Heute ich lerne Deutsch"), false);
});

test("scrambled tiles are never already a right answer, when another order exists", () => {
  const order = ex({ kind: "order", tiles: ["Wo", "wohnst", "du"], answers: ["Wo wohnst du"] });
  let seed = 0;
  const notRandom = () => [0.99, 0.99, 0.99, 0.1, 0.5][seed++ % 5]; // first shuffle = unchanged
  for (let i = 0; i < 20; i++) {
    const tiles = scrambleTiles(order, notRandom);
    assert.deepEqual([...tiles].sort(), [...order.tiles].sort());
    assert.equal(isCorrect(order, tiles.join(" ")), false);
  }
});

test("shuffle keeps every item and does not change the original", () => {
  const items = [1, 2, 3, 4, 5];
  const out = shuffle(items);
  assert.deepEqual([...out].sort(), items);
  assert.deepEqual(items, [1, 2, 3, 4, 5]);
});

test("the answer is shown inside the sentence", () => {
  assert.equal(filled("Ich ___ aus Pakistan. (kommen)", "komme"), "Ich komme aus Pakistan. (kommen)");
  assert.equal(filled("Which sentence is right?", "Ich habe einen Hund."), "Ich habe einen Hund.");
});
