import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator } from "react-native";

import { WordForm } from "@/features/vocabulary/WordForm";
import { useUpdateWord, useWord } from "@/features/vocabulary/api";
import { Centered, ErrorText } from "@/ui/components";

export default function EditWord() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const word = useWord(id);
  const update = useUpdateWord(id);

  if (word.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (word.isError) {
    return (
      <Centered>
        <ErrorText error={word.error} />
      </Centered>
    );
  }

  return (
    <WordForm
      initial={word.data}
      submitLabel="Save"
      busy={update.isPending}
      error={update.error}
      onSubmit={(values) => update.mutate(values, { onSuccess: () => router.back() })}
    />
  );
}
