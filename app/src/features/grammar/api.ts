import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import type { ColorToken } from "@/ui/theme";

type Schemas = components["schemas"];
export type PatternKey = Schemas["PatternKey"];
export type PatternSummary = Schemas["PatternSummaryOut"];
export type Pattern = Schemas["PatternOut"];
export type PatternStats = Schemas["PatternStatsOut"];
export type PatternLevel = Schemas["PatternLevel"];
export type WeakPattern = Schemas["WeakPatternOut"];
export type Evidence = Schemas["EvidenceOut"];
export type MistakeCategory = Schemas["MistakeCategory"];
export type PracticeSet = Schemas["PracticeSetOut"];

export const CATEGORY_LABELS: Record<MistakeCategory, string> = {
  article: "Articles & plurals",
  conjugation: "Verb forms",
  word_order: "Word order",
  case: "Cases",
  preposition: "Prepositions",
  spelling: "Spelling",
  vocabulary: "Word choice",
  listening: "Listening",
  speaking: "Speaking",
  other: "Other",
};

export const LEVEL_LABELS: Record<PatternLevel, string> = {
  not_enough_data: "Not enough answers yet",
  weak: "Weak",
  ok: "OK",
  strong: "Strong",
};

/** Names of palette colors: look them up with `useTheme()`. */
export const LEVEL_COLORS: Record<PatternLevel, ColorToken> = {
  not_enough_data: "muted",
  weak: "danger",
  ok: "warning",
  strong: "success",
};

export function percent(value: number | null): string {
  return value === null ? "–" : `${Math.round(value * 100)}%`;
}

/** "75% right (3 of 4), up from 40%" or "No answers in the last 30 days". */
export function describeStats(s: PatternStats): string {
  if (s.attempts === 0) return "No checked answers in the last 30 days.";
  let text = `${percent(s.accuracy)} right (${s.correct} of ${s.attempts}) in the last 30 days`;
  if (s.previous_accuracy !== null && s.accuracy !== null) {
    const now = Math.round(s.accuracy * 100);
    const before = Math.round(s.previous_accuracy * 100);
    if (now !== before) text += `, ${now > before ? "up" : "down"} from ${before}%`;
  }
  return `${text}.`;
}

const keys = {
  all: ["grammar"] as const,
  patterns: (chapterId?: string) => ["grammar", "patterns", chapterId ?? "all"] as const,
  pattern: (key: string) => ["grammar", "pattern", key] as const,
  weak: ["grammar", "weak"] as const,
  practice: (key: string) => ["grammar", "practice", key] as const,
};

export function usePatterns(chapterId?: string) {
  return useQuery({
    queryKey: keys.patterns(chapterId),
    queryFn: async () =>
      unwrap(await api.GET("/grammar/patterns", { params: { query: { chapter_id: chapterId } } })),
  });
}

export function usePattern(key: PatternKey) {
  return useQuery({
    queryKey: keys.pattern(key),
    queryFn: async () =>
      unwrap(await api.GET("/grammar/patterns/{key}", { params: { path: { key } } })),
  });
}

export function useWeakPatterns() {
  return useQuery({
    queryKey: keys.weak,
    queryFn: async () => unwrap(await api.GET("/grammar/weak", { params: { query: { limit: 5 } } })),
  });
}

export function useSetPatternChapters(key: PatternKey) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (chapterIds: string[]) =>
      unwrap(
        await api.PUT("/grammar/patterns/{key}/chapters", {
          params: { path: { key } },
          body: { chapter_ids: chapterIds },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

/** The fixed exercises for one pattern. They never change, so they are kept for the session. */
export function usePracticeSet(key: PatternKey) {
  return useQuery({
    queryKey: keys.practice(key),
    queryFn: async () =>
      unwrap(await api.GET("/grammar/patterns/{key}/practice", { params: { path: { key } } })),
    staleTime: Infinity,
  });
}

/** Stores one answer. The tracker is refreshed when the session ends, not after every answer. */
export function useAnswerPractice() {
  return useMutation({
    mutationFn: async (body: { exercise_id: string; given: string }) =>
      unwrap(await api.POST("/grammar/practice/answers", { body })),
    retry: 2,
  });
}

/** Call when a practice session ends, so the Grammar page shows the new accuracy. */
export function useRefreshGrammar() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: keys.all, refetchType: "active" });
}
