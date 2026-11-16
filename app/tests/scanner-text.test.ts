// Run with `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  MAX_EXERCISE_CHARS,
  canSend,
  joinBlocks,
  reviewNote,
  wordCount,
} from "../src/features/scanner/text";

test("blocks are joined into editable lines, without empty ones", () => {
  assert.equal(
    joinBlocks(["Übung 3", "  ", "1 Ich ___ nach Hause.  \n", "", "2 Er ___ ein Tisch."]),
    "Übung 3\n1 Ich ___ nach Hause.\n2 Er ___ ein Tisch.",
  );
  assert.equal(joinBlocks([]), "");
  assert.equal(joinBlocks(["", "   "]), "");
});

test("runs of blank lines inside a block are shortened", () => {
  assert.equal(joinBlocks(["a\n\n\n\nb"]), "a\n\nb");
});

test("words are counted across any whitespace", () => {
  assert.equal(wordCount(""), 0);
  assert.equal(wordCount("  Ich   gehe\nnach\tHause. "), 4);
});

test("too little text is flagged and cannot be sent", () => {
  assert.equal(reviewNote(""), null); // nothing yet: the screen says what to do
  assert.equal(reviewNote("Ü 3")?.severity, "warning");
  assert.equal(canSend("Ü 3"), false);
  assert.equal(canSend(""), false);
});

test("too much text is flagged and cannot be sent", () => {
  const long = "wort ".repeat(MAX_EXERCISE_CHARS / 4);
  assert.equal(canSend(long), false);
  assert.match(reviewNote(long)?.text ?? "", /Delete the parts/);
});

test("a normal exercise passes without a note", () => {
  const text = "Ergänzen Sie. 1 Ich ___ nach Hause. (gehen)";
  assert.equal(reviewNote(text), null);
  assert.equal(canSend(text), true);
});

test("the most the server accepts can be sent, one character more cannot", () => {
  const exactly = `${"a ".repeat(MAX_EXERCISE_CHARS / 2 - 1)}ab`;
  assert.equal(exactly.length, MAX_EXERCISE_CHARS);
  assert.equal(canSend(exactly), true);
  assert.equal(canSend(`${exactly}c`), false);
});
