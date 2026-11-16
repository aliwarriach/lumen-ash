import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import type { MistakeCategory, PatternKey } from "@/features/grammar/api";

type Schemas = components["schemas"];
export type Mistake = Schemas["MistakeOut"];
export type MistakeInput = Schemas["MistakeCreate"];
export type MistakeSummary = Schemas["MistakeSummaryOut"];

export type MistakeFilters = {
  category?: MistakeCategory;
  patternKey?: PatternKey;
  wordId?: string;
  chapterId?: string;
  repeatsOnly?: boolean;
};

const keys = {
  all: ["mistakes"] as const,
  list: (f: MistakeFilters) => ["mistakes", "list", f] as const,
  one: (id: string) => ["mistakes", id] as const,
  summary: ["mistakes", "summary"] as const,
};

export function useMistakes(filters: MistakeFilters = {}) {
  return useQuery({
    queryKey: keys.list(filters),
    queryFn: async () =>
      unwrap(
        await api.GET("/mistakes", {
          params: {
            query: {
              category: filters.category,
              pattern_key: filters.patternKey,
              word_id: filters.wordId,
              chapter_id: filters.chapterId,
              repeats_only: filters.repeatsOnly || undefined,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useMistake(id: string) {
  return useQuery({
    queryKey: keys.one(id),
    queryFn: async () =>
      unwrap(await api.GET("/mistakes/{mistake_id}", { params: { path: { mistake_id: id } } })),
  });
}

export function useMistakeSummary() {
  return useQuery({
    queryKey: keys.summary,
    queryFn: async () => unwrap(await api.GET("/mistakes/summary")),
  });
}

// A mistake changes grammar accuracy and adds or removes a retry card in the review queue.
function useMistakeMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.all }),
        queryClient.invalidateQueries({ queryKey: ["grammar"] }),
        queryClient.invalidateQueries({ queryKey: ["reviews"] }),
      ]);
    },
  });
}

export function useCreateMistake() {
  return useMistakeMutation(async (body: MistakeInput) =>
    unwrap(await api.POST("/mistakes", { body })),
  );
}

export function useUpdateMistake(id: string) {
  return useMistakeMutation(async (body: Schemas["MistakeUpdate"]) =>
    unwrap(
      await api.PATCH("/mistakes/{mistake_id}", { params: { path: { mistake_id: id } }, body }),
    ),
  );
}

export function useDeleteMistake(id: string) {
  return useMistakeMutation(async () =>
    unwrap(await api.DELETE("/mistakes/{mistake_id}", { params: { path: { mistake_id: id } } })),
  );
}
