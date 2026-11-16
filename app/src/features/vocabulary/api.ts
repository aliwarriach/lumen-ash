import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type Word = Schemas["WordOut"];
export type WordInput = Schemas["WordCreate"];
export type WordKind = Schemas["WordKind"];
export type WordStage = Schemas["WordStage"];
export type Article = Schemas["Article"];
export type VerbForms = Schemas["VerbForms"];
export type DictionaryEntry = Schemas["DictionaryEntryOut"];
export type Lookup = Schemas["LookupOut"];

export const KIND_LABELS: Record<WordKind, string> = {
  noun: "Noun",
  verb: "Verb",
  adjective: "Adjective",
  adverb: "Adverb",
  phrase: "Phrase",
  other: "Other",
};

export const STAGE_LABELS: Record<WordStage, string> = {
  new: "New",
  learning: "Learning",
  familiar: "Familiar",
  usable: "Usable",
  mastered: "Mastered",
};

export const PERSONS: { key: keyof Schemas["PresentTense"]; label: string }[] = [
  { key: "ich", label: "ich" },
  { key: "du", label: "du" },
  { key: "er_sie_es", label: "er/sie/es" },
  { key: "wir", label: "wir" },
  { key: "ihr", label: "ihr" },
  { key: "sie_Sie", label: "sie/Sie" },
];

/** "der Tisch", "die Eltern", or just the word. */
export function headword(word: { german: string; article?: Article | null }): string {
  return word.article ? `${word.article} ${word.german}` : word.german;
}

const keys = {
  words: ["words"] as const,
  list: (filters: WordFilters) => ["words", "list", filters] as const,
  word: (id: string) => ["words", id] as const,
  lookup: (q: string) => ["dictionary", q] as const,
};

type WordFilters = { chapterId?: string; q?: string };

export function useWords(filters: WordFilters = {}) {
  return useQuery({
    queryKey: keys.list(filters),
    queryFn: async () =>
      unwrap(
        await api.GET("/words", {
          params: { query: { chapter_id: filters.chapterId, q: filters.q || undefined } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useWord(id: string) {
  return useQuery({
    queryKey: keys.word(id),
    queryFn: async () =>
      unwrap(await api.GET("/words/{word_id}", { params: { path: { word_id: id } } })),
    enabled: id.length > 0,
  });
}

export function useLookup(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: keys.lookup(query),
    queryFn: async () =>
      unwrap(await api.GET("/dictionary/lookup", { params: { query: { q: query } } })),
    enabled: query.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000, // dictionary data rarely changes
  });
}

// Word changes also change chapter word counts on the course map.
function useWordMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.words }),
        queryClient.invalidateQueries({ queryKey: ["chapters"] }),
        queryClient.invalidateQueries({ queryKey: ["dictionary"] }),
      ]);
    },
  });
}

export function useCreateWord() {
  return useWordMutation(async (body: WordInput) => unwrap(await api.POST("/words", { body })));
}

export function useUpdateWord(id: string) {
  return useWordMutation(async (body: Schemas["WordUpdate"]) =>
    unwrap(await api.PATCH("/words/{word_id}", { params: { path: { word_id: id } }, body })),
  );
}

export function useDeleteWord(id: string) {
  return useWordMutation(async () =>
    unwrap(await api.DELETE("/words/{word_id}", { params: { path: { word_id: id } } })),
  );
}

/** Pre-fills a new word from a dictionary entry: first meaning and example included. */
export function fromDictionary(entry: DictionaryEntry, chapterId?: string): Partial<WordInput> {
  const isNoun = entry.kind === "noun";
  const isVerb = entry.kind === "verb";
  return {
    dictionary_key: entry.key,
    kind: entry.kind,
    german: entry.lemma,
    article: isNoun ? (entry.articles[0] ?? null) : null,
    plural: isNoun && !entry.plural_only ? (entry.plurals[0] ?? null) : null,
    plural_only: isNoun && entry.plural_only,
    verb_forms: isVerb ? entry.verb_forms : null,
    meaning_en: entry.meanings[0] ?? "",
    example_sentence: entry.example_de ?? null,
    ipa: entry.ipa,
    audio_url: entry.audio_url,
    chapter_id: chapterId ?? null,
  };
}

export function useWordReviews(id: string) {
  return useQuery({
    queryKey: ["words", id, "reviews"],
    queryFn: async () =>
      unwrap(await api.GET("/words/{word_id}/reviews", { params: { path: { word_id: id } } })),
  });
}
