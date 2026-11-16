// Checking practice answers (grammar and sentence lessons) as pure functions, without React
// Native, so `npm test` can run them. Mirrors backend/app/grammar/exercises.py and
// backend/app/sentences/content.py. No AI: plain rules only.
import type { components } from "@/api/schema";
import { UMLAUT_TIP, normalize, onlyUmlautsDiffer } from "@/features/review/grading";

type Schemas = components["schemas"];
export type Blank = Schemas["BlankOut"];

/** One exercise, from either the grammar practice or a sentence lesson. */
export type PracticeItem = {
  id: string;
  kind: "choice" | "fill" | "order" | "bank" | "frame";
  prompt: string;
  english: string | null;
  options: string[];
  tiles: string[];
  distractors?: string[];
  blanks?: Blank[];
  answers: string[];
  exact_case: boolean;
  end: string;
  hint: string;
  why: string;
};

export function isCorrect(ex: PracticeItem, given: string): boolean {
  const answer = normalize(given);
  const accepted = ex.answers.map(normalize);
  if (ex.kind === "choice" || ex.exact_case) return accepted.includes(answer);
  const lower = answer.toLowerCase();
  return accepted.some((a) => a.toLowerCase() === lower);
}

/** A precise tip for a near miss, or null. Still counts as wrong. */
export function nearMiss(ex: PracticeItem, given: string): string | null {
  const answer = normalize(given);
  const expected = normalize(ex.answers[0]);
  if (!answer || isCorrect(ex, given)) return null;
  if (onlyUmlautsDiffer(answer, expected)) return UMLAUT_TIP;
  if (ex.exact_case && answer.toLowerCase() === expected.toLowerCase()) {
    return "Right word, but check the capital letter: German nouns start with one.";
  }
  return null;
}

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const isLetter = (c: string) => c.toLowerCase() !== c.toUpperCase();

/** Why a guided-writing gap is wrong, or null if it is fine. Mirrors `blank_problem`. */
export function blankProblem(blank: Blank, value: string): string | null {
  const text = normalize(value);
  if (!text) return `Fill in ${blank.label}.`;
  if (blank.accepted.length && !blank.accepted.some((a) => a.toLowerCase() === text.toLowerCase())) {
    return `'${text}' isn't one of the words for ${blank.label}.`;
  }
  const first = text.charAt(0);
  if (blank.rule === "capital" && isLetter(first) && first !== first.toUpperCase()) {
    return `${capitalise(blank.label)} starts with a capital letter here.`;
  }
  if (blank.rule === "lower" && isLetter(first) && first !== first.toLowerCase()) {
    return `${capitalise(blank.label)} starts with a small letter here.`;
  }
  if (blank.ends_with && !text.toLowerCase().endsWith(blank.ends_with)) {
    return `${capitalise(blank.label)} should end in -${blank.ends_with}.`;
  }
  return null;
}

/** The frame with the learner's words put in: "Ich heiße Sara. Ich komme aus …" */
export function fillFrame(prompt: string, values: string[]): string {
  let i = 0;
  return prompt.replace(/___/g, () => normalize(values[i++] ?? "") || "___");
}

/** A shuffled copy (Fisher–Yates). `random` is injectable for tests. */
export function shuffle<T>(items: readonly T[], random: () => number = Math.random): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/**
 * The tiles in an order that isn't already an accepted answer, so there is always something to do.
 * Gives up after a few tries (a two-tile sentence may have no other order).
 */
export function scrambleTiles(ex: PracticeItem, random: () => number = Math.random): string[] {
  let tiles = shuffle(ex.tiles, random);
  for (let tries = 0; tries < 10 && isCorrect(ex, tiles.join(" ")); tries++) {
    tiles = shuffle(ex.tiles, random);
  }
  return tiles;
}

/** "Ich ___ aus Pakistan." with the gap filled in, for showing the result. */
export function filled(prompt: string, answer: string): string {
  return prompt.includes("___") ? prompt.replace("___", answer) : answer;
}

/** The right answer as it should be shown after a miss. */
export function shownAnswer(ex: PracticeItem): string {
  if (ex.kind === "order" || ex.kind === "bank") return `${ex.answers[0]}${ex.end}`;
  if (ex.kind === "frame") return ex.answers[0];
  return filled(ex.prompt, ex.answers[0]);
}
