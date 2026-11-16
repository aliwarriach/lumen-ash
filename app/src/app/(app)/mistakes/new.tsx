import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator } from "react-native";

import type { PatternKey } from "@/features/grammar/api";
import { MistakeForm } from "@/features/mistakes/MistakeForm";
import { useCreateMistake } from "@/features/mistakes/api";
import { useWord } from "@/features/vocabulary/api";
import { Centered } from "@/ui/components";

/** Can be opened from a word (?wordId=), a rule (?patternKey=) or a chapter (?chapterId=). */
export default function NewMistake() {
  const { wordId, patternKey, chapterId } = useLocalSearchParams<{
    wordId?: string;
    patternKey?: PatternKey;
    chapterId?: string;
  }>();
  const create = useCreateMistake();
  const word = useWord(wordId ?? "");

  if (wordId && word.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  const w = wordId ? word.data : undefined;

  return (
    <MistakeForm
      initial={{
        pattern_key: patternKey ?? null,
        chapter_id: chapterId ?? w?.chapter_id ?? null,
        words: w ? [{ id: w.id, german: w.german, article: w.article }] : [],
      }}
      submitLabel="Save mistake"
      busy={create.isPending}
      error={create.error}
      onSubmit={(values) =>
        create.mutate(values, {
          onSuccess: (m) => router.replace({ pathname: "/mistakes/[id]", params: { id: m.id } }),
        })
      }
    />
  );
}
