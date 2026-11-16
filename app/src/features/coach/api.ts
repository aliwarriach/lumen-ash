import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import type { ColorToken } from "@/ui/theme";

type Schemas = components["schemas"];
export type CheckResult = Schemas["CheckOut"];
export type Correction = Schemas["CorrectionOut"];
export type WritingTask = Schemas["TaskOut"];
export type Label = Schemas["Label"];
export type Decision = Schemas["Decision"];

export const LABEL_TEXT: Record<Label, string> = {
  confirmed: "Confirmed",
  likely: "Likely",
  uncertain: "Uncertain",
};

/** Names of palette colors: look them up with `useTheme()`. */
export const LABEL_COLORS: Record<Label, ColorToken> = {
  confirmed: "success",
  likely: "primary",
  uncertain: "warning",
};

/** What each label means, shown under the correction. */
export const LABEL_HELP: Record<Label, string> = {
  confirmed: "LanguageTool and our A1 rules agree.",
  likely: "Found by one checker, or two that agree. Worth a look.",
  uncertain: "The checkers disagree or are unsure.",
};

export const TASK_IDEAS = [
  { prompt: "5 sentences about your day", min_sentences: 5 },
  { prompt: "5 sentences about your family", min_sentences: 5 },
  { prompt: "3 sentences about last weekend", min_sentences: 3 },
];

const keys = {
  tasks: ["coach", "tasks"] as const,
  flagged: ["coach", "flagged"] as const,
};

export function useTasks() {
  return useQuery({
    queryKey: keys.tasks,
    queryFn: async () => unwrap(await api.GET("/coach/tasks")),
  });
}

export function useFlagged() {
  return useQuery({
    queryKey: keys.flagged,
    queryFn: async () => unwrap(await api.GET("/coach/flagged")),
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { prompt: string; min_sentences: number }) =>
      unwrap(await api.POST("/coach/tasks", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.tasks }),
  });
}

export function useCheckWriting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { text: string; task_id?: string | null }) =>
      unwrap(await api.POST("/coach/check", { body })),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.tasks }),
        queryClient.invalidateQueries({ queryKey: ["ai", "quota"] }), // "8 sentence checks left"
      ]),
  });
}

/** Accept (adds it to the mistake log), reject or flag one correction. */
export function useDecide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; decision: Decision }) =>
      unwrap(
        await api.POST("/coach/corrections/{correction_id}/{decision}", {
          params: { path: { correction_id: v.id, decision: v.decision } },
        }),
      ),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.flagged }),
        // An accepted correction becomes a mistake, a retry card and grammar evidence.
        queryClient.invalidateQueries({ queryKey: ["mistakes"] }),
        queryClient.invalidateQueries({ queryKey: ["grammar"] }),
        queryClient.invalidateQueries({ queryKey: ["reviews"] }),
      ]),
  });
}
