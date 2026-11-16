// Small pure helpers for the add-word form. No React Native imports, so `npm test` can run them.

export type GuessedKind = "noun" | "verb" | "adjective" | "phrase";

/**
 * A first guess at the word type from how it is written, so the learner usually has nothing to
 * pick: a space means a phrase, a capital letter a noun (German capitalises every noun), a lower
 * case word ending in -en/-ern/-eln a verb. Anything else is most often an adjective in A1.
 * It is only a starting point: the type is always shown and can be changed with one tap.
 */
export function guessKind(german: string): GuessedKind {
  const word = german.trim();
  if (/\s/.test(word)) return "phrase";
  const first = word.charAt(0);
  if (first && first !== first.toLowerCase()) return "noun";
  if (word.length > 3 && /(en|ern|eln)$/.test(word)) return "verb";
  return "adjective";
}

type SummaryInput = {
  kind: string;
  german: string;
  article: string | null;
  plural: string | null;
  pluralOnly: boolean;
  verb: {
    present?: Partial<Record<"ich" | "du" | "er_sie_es", string | null>> | null;
    past_participle?: string | null;
    auxiliary?: string | null;
  } | null;
};

/** The few lines that say what the dictionary filled in, so the learner can check them at a glance. */
export function summarize(w: SummaryInput): string[] {
  if (w.kind === "noun") {
    const head = w.pluralOnly ? `die ${w.german}` : [w.article, w.german].filter(Boolean).join(" ");
    const lines = [head];
    if (w.pluralOnly) lines.push("plural only");
    else if (w.plural) lines.push(`plural: die ${w.plural}`);
    return lines;
  }
  if (w.kind === "verb" && w.verb) {
    const present = [
      w.verb.present?.ich && `ich ${w.verb.present.ich}`,
      w.verb.present?.du && `du ${w.verb.present.du}`,
      w.verb.present?.er_sie_es && `er/sie/es ${w.verb.present.er_sie_es}`,
    ].filter(Boolean);
    const perfect = w.verb.past_participle
      ? `Perfekt: ${w.verb.auxiliary ? `${w.verb.auxiliary} ` : ""}${w.verb.past_participle}`
      : null;
    return [w.german, present.join(" · "), perfect ?? ""].filter(Boolean);
  }
  return [w.german];
}
