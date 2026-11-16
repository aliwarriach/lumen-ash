// Run with `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  answerLine,
  filterByArticle,
  kindLabel,
  pickRound,
  quizNouns,
  scoreLine,
} from "../src/features/vocabulary/articleRules";

type Article = "der" | "die" | "das";

function word(
  german: string,
  article: Article | null,
  extra: Partial<{ kind: string; plural: string | null; plural_only: boolean }> = {},
) {
  return {
    id: german,
    kind: "noun",
    german,
    article,
    plural: null as string | null,
    plural_only: false,
    meaning_en: german.toLowerCase(),
    ...extra,
  };
}

test("only nouns with an article that are not plural-only are asked", () => {
  const words = [
    word("Tisch", "der"),
    word("Eltern", "die", { plural_only: true }),
    word("gehen", null, { kind: "verb" }),
    word("Hallo", null),
    word("Lampe", "die"),
  ];
  assert.deepEqual(
    quizNouns(words).map((w) => w.german),
    ["Tisch", "Lampe"],
  );
});

test("a round has no repeats, is capped, and is shuffled by the random source", () => {
  const pool = Array.from({ length: 25 }, (_, i) => i);
  const round = pickRound(pool, 10);
  assert.equal(round.length, 10);
  assert.equal(new Set(round).size, 10);
  assert.deepEqual(pickRound([1, 2, 3], 10).sort(), [1, 2, 3]); // a small pool gives a small round
  // random() === 0 always picks index 0 to swap with: a fixed, repeatable order.
  assert.deepEqual(pickRound([1, 2, 3, 4], 4, () => 0), [2, 3, 4, 1]);
  assert.deepEqual(pool.length, 25); // the pool itself is left alone
});

test("the answer line shows the article, the word and its plural", () => {
  assert.equal(answerLine({ article: "das", german: "Fenster", plural: "Fenster" }), "das Fenster · die Fenster");
  assert.equal(answerLine({ article: "der", german: "Tisch", plural: null }), "der Tisch");
});

test("the filter keeps one article, or everything", () => {
  const words = [word("Tisch", "der"), word("Lampe", "die"), word("gehen", null, { kind: "verb" })];
  assert.equal(filterByArticle(words, "all").length, 3);
  assert.deepEqual(
    filterByArticle(words, "die").map((w) => w.german),
    ["Lampe"],
  );
  assert.equal(filterByArticle(words, "das").length, 0);
});

test("word types and scores read plainly", () => {
  assert.equal(kindLabel("adjective"), "adj.");
  assert.equal(kindLabel("verb"), "verb");
  assert.equal(scoreLine(7, 10), "7 of 10 right");
});
