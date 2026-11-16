import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import type { Label } from "@/features/coach/api";

type Schemas = components["schemas"];
export type ExerciseHelp = Schemas["ScanHelpOut"];
export type ExerciseItem = Schemas["ScanItemOut"];

/** What each label means for an answer (not the same as for a correction of the learner's text). */
export const ANSWER_LABEL_HELP: Record<Label, string> = {
  confirmed: "The AI's answer. Our dictionary proves the verb ending and LanguageTool agrees.",
  likely: "The AI's answer. LanguageTool found nothing wrong with the sentence, but nothing proves it.",
  uncertain: "The AI's answer, but a checker objected or the AI was unsure.",
};

/** Asks the AI for hints and answers. Stores nothing: not the text, not the answers. */
export function useExerciseHelp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(await api.POST("/scanner/help", { body: { text } })),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["ai", "quota"] }), // "9 exercise helps left"
  });
}
