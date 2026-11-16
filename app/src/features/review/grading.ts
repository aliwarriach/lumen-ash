// Mirrors backend/app/review/grading.py so feedback is instant, even offline.
// The server re-checks every answer; its result is the one that counts.
import type { components } from "@/api/schema";

type Word = components["schemas"]["QueueWord"];

export type Grade = { correct: boolean; expected: string; feedback: string | null };

export function normalize(text: string): string {
  return text
    .normalize("NFC")
    .replace(/[’‘]/g, "'")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[.!?]+$/, "")
    .trim();
}

export function expectedAnswer(word: Word): string {
  if (word.kind === "noun") {
    const article = word.plural_only ? "die" : word.article;
    if (article) return `${article} ${word.german}`;
  }
  return word.german;
}

const ARTICLES = new Set(["der", "die", "das"]);

export const UMLAUT_TIP =
  "Check ä, ö, ü and ß: they are letters of their own. Hold a, o, u or s on the keyboard to type them.";

const WITHOUT_DOTS: Record<string, string> = { ä: "a", ö: "o", ü: "u", ß: "ss" };
const SPELLED_OUT: Record<string, string> = { ä: "ae", ö: "oe", ü: "ue", ß: "ss" };
const swap = (text: string, map: Record<string, string>) => text.replace(/[äöüß]/g, (c) => map[c]);

/**
 * The answer is the expected text with an umlaut or ß left out or spelled out: "Madchen" or
 * "Maedchen" for Mädchen, "Strasse" for Straße, "Mutter" for the plural Mütter. Still wrong, but
 * it deserves to be told exactly what is wrong. Both arguments must already be normalised.
 */
export function onlyUmlautsDiffer(given: string, expected: string): boolean {
  const g = given.toLowerCase();
  const e = expected.toLowerCase();
  if (g === e || !/[äöüß]/.test(e)) return false;
  return g === swap(e, SPELLED_OUT) || swap(g, WITHOUT_DOTS) === swap(e, WITHOUT_DOTS);
}

export function checkProduce(word: Word, answer: string): Grade {
  const shown = expectedAnswer(word);
  // Both sides in the same Unicode form: "ä" can be stored as one character or as a + dots.
  const expected = normalize(shown);
  const given = normalize(answer);
  if (given === expected) return { correct: true, expected: shown, feedback: null };

  let feedback: string | null = null;
  if (given.toLowerCase() === expected.toLowerCase()) {
    feedback = "Check the capital letters: German nouns start with a capital.";
  } else if (onlyUmlautsDiffer(given, expected)) {
    feedback = UMLAUT_TIP;
  } else if (word.kind === "noun" && expected.includes(" ")) {
    const [article, noun] = splitFirst(expected);
    const [givenArticle, givenNoun] = splitFirst(given);
    if (given === noun || (givenNoun === noun && !ARTICLES.has(givenArticle))) {
      feedback = `Include the article: ${article}.`;
    } else if (givenNoun === noun) {
      feedback = `Wrong article: it's ${article} ${noun}.`;
    }
  }
  return { correct: false, expected: shown, feedback };
}

export function checkArticle(word: Word, article: string | null, plural: string): Grade {
  const expectedArticle = word.plural_only ? "die" : word.article;
  const asksPlural = Boolean(word.plural) && !word.plural_only;
  const parts = [expectedArticle ? `${expectedArticle} ${word.german}` : word.german];
  if (asksPlural) parts.push(`die ${word.plural}`);

  const problems: string[] = [];
  if (expectedArticle && (article ?? "").trim().toLowerCase() !== expectedArticle) {
    problems.push(`The article is ${expectedArticle}.`);
  }
  const expectedPlural = normalize(word.plural ?? "");
  if (asksPlural && normalize(plural) !== expectedPlural) {
    problems.push(`The plural is die ${word.plural}.`);
    if (onlyUmlautsDiffer(normalize(plural), expectedPlural)) problems.push(UMLAUT_TIP);
  }
  return { correct: problems.length === 0, expected: parts.join(" · "), feedback: problems.join(" ") || null };
}

/** Error-retry cards: is this the corrected version of the logged mistake? */
export function checkCorrection(correct: string, answer: string): Grade {
  const given = normalize(answer);
  const expected = normalize(correct);
  if (given === expected) return { correct: true, expected: correct, feedback: null };
  const words = (t: string) => t.split(" ").filter(Boolean).sort().join(" ");
  let feedback: string | null = null;
  if (given.toLowerCase() === expected.toLowerCase()) {
    feedback = "Check the capital letters.";
  } else if (onlyUmlautsDiffer(given, expected)) {
    feedback = UMLAUT_TIP;
  } else if (given && words(given) === words(expected)) {
    feedback = "The right words, but in the wrong order.";
  }
  return { correct: false, expected: correct, feedback };
}

/** Does the sentence use the word (any listed form; both parts of a separable verb)? */
export function usesWord(word: Word, sentence: string): boolean {
  const tokens = new Set(sentence.normalize("NFC").toLowerCase().match(/[\p{L}\d_]+/gu) ?? []);
  const forms = new Set<string>([word.german]);
  if (word.plural) forms.add(word.plural);
  const vf = word.verb_forms;
  if (vf) {
    Object.values(vf.present ?? {}).forEach((f) => f && forms.add(f));
    if (vf.past_participle) forms.add(vf.past_participle);
    if (vf.preterite) forms.add(vf.preterite);
  }
  return [...forms].some((form) => {
    const parts = form.toLowerCase().split(/\s+/).filter(Boolean);
    return parts.length > 0 && parts.every((p) => tokens.has(p));
  });
}

function splitFirst(text: string): [string, string] {
  const i = text.indexOf(" ");
  return i === -1 ? [text, ""] : [text.slice(0, i), text.slice(i + 1)];
}
