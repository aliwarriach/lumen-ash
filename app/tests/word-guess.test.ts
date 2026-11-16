// Run with `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import { guessKind, summarize } from "../src/features/vocabulary/guess";

test("the word type is guessed from how the word is written", () => {
  assert.equal(guessKind("Tisch"), "noun"); // German capitalises every noun
  assert.equal(guessKind("Äpfel"), "noun");
  assert.equal(guessKind("aufstehen"), "verb");
  assert.equal(guessKind("wandern"), "verb");
  assert.equal(guessKind("sammeln"), "verb");
  assert.equal(guessKind("schnell"), "adjective");
  assert.equal(guessKind("Wie geht's"), "phrase");
  assert.equal(guessKind("  gut "), "adjective");
  assert.equal(guessKind(""), "adjective");
  // Short words ending in "en" are not verbs ("den", "wen" are not infinitives).
  assert.equal(guessKind("den"), "adjective");
});

test("a noun's summary names the article and the plural", () => {
  assert.deepEqual(
    summarize({ kind: "noun", german: "Tisch", article: "der", plural: "Tische", pluralOnly: false, verb: null }),
    ["der Tisch", "plural: die Tische"],
  );
  assert.deepEqual(
    summarize({ kind: "noun", german: "Eltern", article: null, plural: null, pluralOnly: true, verb: null }),
    ["die Eltern", "plural only"],
  );
  assert.deepEqual(
    summarize({ kind: "noun", german: "Zeit", article: "die", plural: null, pluralOnly: false, verb: null }),
    ["die Zeit"],
  );
});

test("a verb's summary shows three present forms and the Perfekt", () => {
  assert.deepEqual(
    summarize({
      kind: "verb",
      german: "gehen",
      article: null,
      plural: null,
      pluralOnly: false,
      verb: {
        present: { ich: "gehe", du: "gehst", er_sie_es: "geht" },
        past_participle: "gegangen",
        auxiliary: "sein",
      },
    }),
    ["gehen", "ich gehe · du gehst · er/sie/es geht", "Perfekt: sein gegangen"],
  );
  assert.deepEqual(
    summarize({ kind: "verb", german: "sein", article: null, plural: null, pluralOnly: false, verb: { present: {} } }),
    ["sein"],
  );
});

test("other word types are just the word", () => {
  assert.deepEqual(
    summarize({ kind: "adjective", german: "schnell", article: null, plural: null, pluralOnly: false, verb: null }),
    ["schnell"],
  );
});
