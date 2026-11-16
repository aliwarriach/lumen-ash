// Run with `npm test`. Tidying up what the phone read from a photo, and noticing a bad reading.
// The examples are written by hand from the usual ways text recognition gets German wrong; they
// have not been collected from real photos yet (see ROADMAP.md, device test steps).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  cleanReading,
  forSending,
  looksMisread,
  normalizeGaps,
  readingQuality,
  reviewNote,
} from "../src/features/scanner/text";

test("every form of a printed gap becomes ___", () => {
  const cases: [string, string][] = [
    ["Ich _ _ _ _ nach Hause.", "Ich ___ nach Hause."],
    ["Ich ________ nach Hause.", "Ich ___ nach Hause."],
    ["Ich __ nach Hause.", "Ich ___ nach Hause."],
    ["Ich ..... nach Hause.", "Ich ___ nach Hause."],
    ["Ich . . . . nach Hause.", "Ich ___ nach Hause."],
    ["Ich … nach Hause.", "Ich ___ nach Hause."],
    ["Ich ----- nach Hause.", "Ich ___ nach Hause."],
    ["Ich — — — nach Hause.", "Ich ___ nach Hause."],
    ["Ich _ nach Hause.", "Ich ___ nach Hause."],
    ["Er komm_ _ _ aus Wien.", "Er komm___ aus Wien."], // a missing ending stays on its word
    ["Wie ___ du?", "Wie ___ du?"], // already right
  ];
  for (const [read, expected] of cases) assert.equal(normalizeGaps(read), expected, read);
});

test("ordinary punctuation is not taken for a gap", () => {
  for (const text of ["Ich gehe. Du gehst.", "E-Mail, S-Bahn - und zurück.", "z. B. um 9.30 Uhr", "Hallo .. ja"]) {
    assert.equal(normalizeGaps(text), text);
  }
});

test("a word split over two lines is joined", () => {
  assert.equal(cleanReading("Ich esse zum Früh-\nstück ein Brot."), "Ich esse zum Frühstück ein Brot.");
  assert.equal(cleanReading("die Kranken-  \n  versicherung"), "die Krankenversicherung");
  // These hyphens are real.
  assert.equal(cleanReading("Haupt-\nund Nebensatz"), "Haupt- und Nebensatz");
  assert.equal(cleanReading("meine E-Mail-\nAdresse"), "meine E-Mail-Adresse");
  // A new line that isn't the rest of a word is left where it is.
  assert.equal(cleanReading("1 Ich gehe.\n2 Du gehst."), "1 Ich gehe.\n2 Du gehst.");
  assert.equal(cleanReading("Wörter -\nsuchen"), "Wörter -\nsuchen");
});

test("ß read as a capital B or a beta is put back", () => {
  const cases: [string, string][] = [
    ["Ich heiBe Ali.", "Ich heiße Ali."],
    ["Die StraBe ist groB.", "Die Straße ist groß."],
    ["FuBball macht SpaB!", "Fußball macht Spaß!"],
    ["Ich heiβe Ali.", "Ich heiße Ali."],
  ];
  for (const [read, expected] of cases) assert.equal(cleanReading(read), expected, read);
  // A real capital B stays.
  for (const text of ["Das Buch von Bernd", "AB Seite 24, KB Seite 30", "Ich kaufe bei eBay.", "z.B. ein Brot"]) {
    assert.equal(cleanReading(text), text);
  }
});

test("capital I and small l are told apart where German leaves no doubt", () => {
  const cases: [string, string][] = [
    ["lch komme aus ltalien.", "Ich komme aus Italien."],
    ["Wie heißen Sie? lst das lhr Buch?", "Wie heißen Sie? Ist das Ihr Buch?"],
    ["lm Sommer, ln Berlin", "Im Sommer, In Berlin"],
    ["|ch bin Ali.", "Ich bin Ali."],
    ["Die SchuIe hat vieIe Lehrer.", "Die Schule hat viele Lehrer."],
  ];
  for (const [read, expected] of cases) assert.equal(cleanReading(read), expected, read);
  // Real words that start with l, and the abbreviations that start with l + consonant.
  for (const text of ["lernen, lesen, leben", "lt. Plan", "Kapitel lll", "Ich lerne Deutsch."]) {
    assert.equal(cleanReading(text), text);
  }
});

test("umlauts come out in one Unicode form", () => {
  const decomposed = "Mädchen".normalize("NFD");
  assert.notEqual(decomposed, "Mädchen");
  assert.equal(cleanReading(`Das ${decomposed} ist müde.`), "Das Mädchen ist müde.");
  assert.equal(forSending(` Das ${decomposed} _ _ _ müde. `), "Das Mädchen ___ müde.");
});

test("correct German passes through unchanged", () => {
  const text = [
    "3 Ergänzen Sie.",
    "a) Ich ___ aus Pakistan. (kommen)",
    "b) Wie heißt du? - Ich heiße Ali.",
    "c) Wir fahren mit der U-Bahn zum Bahnhof.",
    "d) Lehrer(in), der/die Student*in, anna@web.de",
  ].join("\n");
  assert.equal(cleanReading(text), text);
});

test("what is sent keeps the learner's own words", () => {
  // Typed text gets its gaps and Unicode tidied, never its letters.
  assert.equal(forSending("lch heiBe ..... "), "lch heiBe ___");
});

test("a well read exercise is not called misread", () => {
  const text = [
    "Ergänzen Sie die Verben. Kurs A1, Seite 24, Aufgabe 2a",
    "1 Ich ___ aus Pakistan. (kommen)",
    "2 Er schreibt bei WhatsApp: Hallo! Wie geht's?",
    "3 Lehrer(in), der/die Student*in, anna@web.de, 9.30 Uhr, DVD, z.B.",
  ].join("\n");
  assert.equal(readingQuality(text).odd, 1); // WhatsApp
  assert.equal(looksMisread(text), false);
  assert.equal(reviewNote(text), null);
});

test("a badly read photo gets a warning that says what to do", () => {
  const text = "Erg#nzen S1e d|e Verbcn. 1ch k0mme aus Pkstn. Wle he!sst dU?";
  assert.equal(looksMisread(text), true);
  const note = reviewNote(text);
  assert.equal(note?.severity, "warning");
  assert.match(note?.text ?? "", /Take the photo again/);
  // One or two odd words in a long text are not a bad reading.
  assert.equal(looksMisread("Ich schreibe bei WhatsApp und YouTube. Wie ___ du? Ich heiße Ali."), false);
});

test("text without any gap gets a gentle reminder, not a warning", () => {
  const note = reviewNote("Schreiben Sie Fragen. Wo wohnen Sie?");
  assert.equal(note?.severity, "info");
  assert.match(note?.text ?? "", /___/);
  // Any form of gap counts: it will be sent as ___.
  assert.equal(reviewNote("Ich ..... nach Hause. (gehen)"), null);
});
