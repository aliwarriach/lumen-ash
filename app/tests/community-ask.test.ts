// Run with `npm test`. "Ask the Community": what goes into the card above a question.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  LINES_MAX,
  LINE_MAX,
  TITLE_MAX,
  aboutChapter,
  aboutExercise,
  aboutGrammar,
  aboutResource,
  aboutScannedItem,
  aboutWord,
  card,
  clip,
  describe,
} from "../src/features/community/ask";

const noun = {
  kind: "noun",
  german: "Tisch",
  article: "der",
  plural: "Tische",
  plural_only: false,
  meaning_en: "table",
  example_sentence: "Der Tisch ist groß.",
};

test("a word shares its article, meaning, plural and example", () => {
  assert.deepEqual(aboutWord(noun), {
    kind: "word",
    title: "der Tisch",
    lines: ["table", "Plural: die Tische", "“Der Tisch ist groß.”"],
  });
  const verb = { ...noun, kind: "verb", german: "gehen", article: null, plural: null, example_sentence: null, meaning_en: "to go" };
  assert.deepEqual(aboutWord(verb), { kind: "word", title: "gehen", lines: ["to go"] });
  assert.deepEqual(aboutWord({ ...noun, german: "Eltern", article: "die", plural: null, plural_only: true }).lines, [
    "table",
    "Plural only",
    "“Der Tisch ist groß.”",
  ]);
});

test("an exercise carries the task, the question and, once given, my answer", () => {
  const item = { prompt: "Ich ___ aus Pakistan.", english: "I come from Pakistan." };
  const before = aboutExercise("Verben im Präsens · 3 of 10", "Type the missing word", item);
  assert.deepEqual(before.lines, ["Type the missing word", "Ich ___ aus Pakistan.", "I come from Pakistan."]);
  const after = aboutExercise("Verben im Präsens · 3 of 10", "Type the missing word", item, "kommt");
  assert.equal(after.lines?.at(-1), "My answer: kommt");
  assert.deepEqual(aboutScannedItem(null, { number: "2.", task: "Wir ___ Deutsch." }, "lernen"), {
    kind: "exercise",
    title: "An exercise from my book",
    lines: ["2. Wir ___ Deutsch.", "My answer: lernen"],
  });
});

test("a grammar rule is shared as a short excerpt, a resource without its link", () => {
  const rule = aboutGrammar({ title: "Perfekt mit haben", category: "Verbs", explanation: "x ".repeat(400) });
  assert.equal(rule.kind, "grammar");
  assert.ok((rule.lines?.[1].length ?? 0) <= 220 && rule.lines?.[1].endsWith("…"));
  const res = aboutResource({ title: "Hörtext 2", reference: "S. 24, Ü 3" }, "Audio", 4);
  assert.deepEqual(res, { kind: "resource", title: "Hörtext 2", lines: ["Kapitel 4 · Audio · S. 24, Ü 3"] });
  assert.ok(!JSON.stringify(res).includes("http"));
  assert.deepEqual(aboutChapter({ number: 4, title: "Essen und Trinken", topics: ["Lebensmittel", "im Café"] }), {
    kind: "lesson",
    title: "Kapitel 4: Essen und Trinken",
    lines: ["Lebensmittel · im Café"],
  });
});

test("a card is tidied and kept within the server's limits", () => {
  const big = card("exercise", "T".repeat(500), ["", "  a   b  ", ...Array.from({ length: 10 }, () => "y".repeat(400))]);
  assert.equal(big.title.length, TITLE_MAX);
  assert.equal(big.lines?.length, LINES_MAX);
  assert.equal(big.lines?.[0], "a b");
  assert.equal(big.lines?.[1].length, LINE_MAX);
  assert.equal(clip("kurz", 10), "kurz");
  assert.equal(describe(aboutWord(noun)), "Shared word: der Tisch. table. Plural: die Tische. “Der Tisch ist groß.”");
});
