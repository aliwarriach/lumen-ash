import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type ChapterSummary = Schemas["ChapterSummaryOut"];
export type Chapter = Schemas["ChapterOut"];
export type Resource = Schemas["ResourceOut"];
export type ResourceKind = Schemas["ResourceKind"];
export type ChapterStatus = Schemas["ChapterStatus"];
export type ChapterInput = Schemas["ChapterCreate"];
export type ResourceInput = Schemas["ResourceCreate"];

export const RESOURCE_KINDS: { kind: ResourceKind; label: string }[] = [
  { kind: "book_page", label: "Book page" },
  { kind: "workbook_exercise", label: "Workbook exercise" },
  { kind: "audio", label: "Audio" },
  { kind: "video", label: "Video" },
  { kind: "exercise", label: "Exercise" },
  { kind: "other", label: "Other" },
];

export function kindLabel(kind: ResourceKind): string {
  return RESOURCE_KINDS.find((k) => k.kind === kind)?.label ?? kind;
}

export const STATUS_LABELS: Record<ChapterStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
};

const keys = {
  chapters: ["chapters"] as const,
  chapter: (id: string) => ["chapters", id] as const,
};

export function useChapters() {
  return useQuery({
    queryKey: keys.chapters,
    queryFn: async () => unwrap(await api.GET("/chapters")),
  });
}

export function useChapter(id: string) {
  return useQuery({
    queryKey: keys.chapter(id),
    queryFn: async () =>
      unwrap(await api.GET("/chapters/{chapter_id}", { params: { path: { chapter_id: id } } })),
  });
}

// Every course change refreshes the map and the open chapter.
function useCourseMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.chapters }),
  });
}

export function useCreateChapter() {
  return useCourseMutation(async (body: ChapterInput) =>
    unwrap(await api.POST("/chapters", { body })),
  );
}

export function useUpdateChapter(id: string) {
  return useCourseMutation(async (body: Schemas["ChapterUpdate"]) =>
    unwrap(
      await api.PATCH("/chapters/{chapter_id}", { params: { path: { chapter_id: id } }, body }),
    ),
  );
}

export function useDeleteChapter(id: string) {
  return useCourseMutation(async () =>
    unwrap(await api.DELETE("/chapters/{chapter_id}", { params: { path: { chapter_id: id } } })),
  );
}

export function useCreateResource(chapterId: string) {
  return useCourseMutation(async (body: ResourceInput) =>
    unwrap(
      await api.POST("/chapters/{chapter_id}/resources", {
        params: { path: { chapter_id: chapterId } },
        body,
      }),
    ),
  );
}

export function useUpdateResource() {
  return useCourseMutation(
    async ({ id, ...body }: Schemas["ResourceUpdate"] & { id: string }) =>
      unwrap(
        await api.PATCH("/resources/{resource_id}", { params: { path: { resource_id: id } }, body }),
      ),
  );
}

export function useDeleteResource() {
  return useCourseMutation(async (id: string) =>
    unwrap(await api.DELETE("/resources/{resource_id}", { params: { path: { resource_id: id } } })),
  );
}

// "Sich vorstellen, Zahlen" or one per line -> ["Sich vorstellen", "Zahlen"]
export function parseTopics(text: string): string[] {
  return text
    .split(/[\n,]/)
    .map((t) => t.trim())
    .filter(Boolean);
}
