// "Ask the Community": turns what the learner is looking at into the small card that goes above
// their question in the group chat. Plain rules, no AI. Pure functions, no React Native, so they
// are tested with node:test (tests/community-ask.test.ts).
//
// Only text goes into a card: never a link, an id, an email or anything another person's phone
// would open. Course text is shared as short excerpts (the server also caps every card at a title
// of 120 characters and 6 lines of 300).
import type { components } from "../../api/schema";

export type Attachment = components["schemas"]["CommunityAttachment"];
export type AttachmentKind = Attachment["kind"];

export const TITLE_MAX = 120;
export const LINE_MAX = 300;
export const LINES_MAX = 6;
/** A long explanation (a grammar rule) is cut to this, as an excerpt. */
export const EXCERPT_MAX = 220;

export const KIND_LABELS: Record<AttachmentKind, string> = {
  word: "Word",
  exercise: "Exercise",
  lesson: "Chapter",
  grammar: "Grammar rule",
  resource: "Course material",
};

/** Quick starts for the question. Tapping one writes it into the box, where it can be changed. */
export const ASK_PROMPTS = [
  "I don't understand this.",
  "Is my answer right?",
  "What should I do here?",
  "How do I say this correctly?",
] as const;

/** One line of a card: spaces collapsed, cut with "…" at `max`. */
export function clip(text: string, max: number): string {
  const flat = text.split(/\s+/).filter(Boolean).join(" ");
  return flat.length <= max ? flat : flat.slice(0, max - 1).trimEnd() + "…";
}

/** A card with its title and lines tidied the way the server will tidy them. */
export function card(kind: AttachmentKind, title: string, lines: (string | null | undefined)[]): Attachment {
  return {
    kind,
    title: clip(title, TITLE_MAX),
    lines: lines
      .map((l) => (l ? clip(l, LINE_MAX) : ""))
      .filter(Boolean)
      .slice(0, LINES_MAX),
  };
}

type WordLike = {
  kind: string;
  german: string;
  article: string | null;
  plural: string | null;
  plural_only: boolean;
  meaning_en: string;
  example_sentence: string | null;
};

export function aboutWord(w: WordLike): Attachment {
  const head = w.article ? `${w.article} ${w.german}` : w.german;
  const plural =
    w.kind !== "noun" ? null : w.plural_only ? "Plural only" : w.plural ? `Plural: die ${w.plural}` : null;
  return card("word", head, [w.meaning_en, plural, w.example_sentence ? `“${w.example_sentence}”` : null]);
}

type ExerciseLike = { prompt: string; english?: string | null };

/**
 * A practice exercise. `where` names it (the rule or lesson and the question number); `task` says
 * what kind of exercise it is; the learner's answer is added once they have given one.
 */
export function aboutExercise(
  where: string,
  task: string,
  item: ExerciseLike,
  myAnswer?: string | null,
): Attachment {
  return card("exercise", where, [
    task,
    item.prompt,
    item.english ?? null,
    myAnswer ? `My answer: ${myAnswer}` : null,
  ]);
}

/** One item of an exercise the learner scanned from their book or worksheet. */
export function aboutScannedItem(
  instruction: string | null,
  item: { number: string | null; task: string },
  myAnswer?: string | null,
): Attachment {
  return card("exercise", instruction ? clip(instruction, TITLE_MAX) : "An exercise from my book", [
    item.number ? `${item.number} ${item.task}` : item.task,
    myAnswer ? `My answer: ${myAnswer}` : null,
  ]);
}

export function aboutGrammar(p: { title: string; category: string; explanation: string }): Attachment {
  return card("grammar", p.title, [p.category, clip(p.explanation, EXCERPT_MAX)]);
}

export function aboutChapter(c: { number: number; title: string; topics: string[] }): Attachment {
  return card("lesson", `Kapitel ${c.number}: ${c.title}`, [c.topics.length ? c.topics.join(" · ") : null]);
}

/** A course resource: its name and where it is in the book, never its web link. */
export function aboutResource(
  r: { title: string; reference: string | null },
  kindLabel: string,
  chapterNumber: number | null,
  myAnswer?: string | null,
): Attachment {
  const where = [chapterNumber !== null ? `Kapitel ${chapterNumber}` : null, kindLabel, r.reference]
    .filter(Boolean)
    .join(" · ");
  return card("resource", r.title, [where, myAnswer ? `My answer: ${myAnswer}` : null]);
}

/** What a screen reader says for a card, e.g. "Shared word: der Tisch. table". */
export function describe(a: Attachment): string {
  return [`Shared ${KIND_LABELS[a.kind].toLowerCase()}: ${a.title}`, ...(a.lines ?? [])].join(". ");
}
