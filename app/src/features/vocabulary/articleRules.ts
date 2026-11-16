// The Words tab's article quiz and filter: plain rules over the learner's own nouns, no AI.
// Pure functions, no React Native, so they are tested with node:test (tests/article-rules.test.ts).
import type { components } from "../../api/schema";

type Article = components["schemas"]["Article"];

/** The part of a saved word the quiz needs. */
type WordLike = {
  id: string;
  kind: string;
  german: string;
  article: Article | null;
  plural: string | null;
  plural_only: boolean;
  meaning_en: string;
};

export const ARTICLES: readonly Article[] = ["der", "die", "das"];

export const GENDER: Record<Article, string> = {
  der: "masculine",
  die: "feminine",
  das: "neuter",
};

/** Questions in one round. */
export const ROUND_SIZE = 10;

/** The nouns that can be asked: they have an article, and are not plural-only (always "die"). */
export function quizNouns<T extends WordLike>(words: readonly T[]): (T & { article: Article })[] {
  return words.filter(
    (w): w is T & { article: Article } => w.kind === "noun" && w.article !== null && !w.plural_only,
  );
}

/** A random round of up to `size` different nouns (Fisher-Yates; `random` is injectable for tests). */
export function pickRound<T>(pool: readonly T[], size = ROUND_SIZE, random: () => number = Math.random): T[] {
  const copy = [...pool];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j]!, copy[i]!];
  }
  return copy.slice(0, size);
}

/** "das Fenster · die Fenster": shown after an answer. */
export function answerLine(w: Pick<WordLike, "german" | "plural"> & { article: Article }): string {
  const single = `${w.article} ${w.german}`;
  return w.plural ? `${single} · die ${w.plural}` : single;
}

export type ArticleFilter = "all" | Article;

/** The list under the quiz: everything, or only the nouns with one article. */
export function filterByArticle<T extends Pick<WordLike, "article">>(
  words: readonly T[],
  filter: ArticleFilter,
): T[] {
  return filter === "all" ? [...words] : words.filter((w) => w.article === filter);
}

/** A short word-type label for the list's first column when a word has no article. */
export function kindLabel(kind: string): string {
  switch (kind) {
    case "adjective":
      return "adj.";
    case "adverb":
      return "adv.";
    case "other":
      return "other";
    default:
      return kind;
  }
}

/** "7 of 10 right". */
export function scoreLine(correct: number, total: number): string {
  return `${correct} of ${total} right`;
}
