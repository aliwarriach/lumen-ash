import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type LessonSummary = Schemas["LessonSummaryOut"];
export type Lesson = Schemas["LessonOut"];

const keys = {
  all: ["sentences"] as const,
  lessons: ["sentences", "lessons"] as const,
  lesson: (id: string) => ["sentences", "lesson", id] as const,
};

export function useLessons() {
  return useQuery({
    queryKey: keys.lessons,
    queryFn: async () => unwrap(await api.GET("/sentences/lessons")),
  });
}

export function useLesson(id: string) {
  return useQuery({
    queryKey: keys.lesson(id),
    queryFn: async () =>
      unwrap(await api.GET("/sentences/lessons/{lesson_id}", { params: { path: { lesson_id: id } } })),
    // The chapter lessons never change; "From my words" changes when words are added.
    staleTime: id === "my-words" ? 0 : Infinity,
  });
}

export function useSaveLessonResult(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { right: number; total: number }) =>
      unwrap(
        await api.POST("/sentences/lessons/{lesson_id}/result", {
          params: { path: { lesson_id: id } },
          body,
        }),
      ),
    retry: 2,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.lessons }),
  });
}
