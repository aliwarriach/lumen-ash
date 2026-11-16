import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator } from "react-native";

import { useChapter, useUpdateChapter } from "@/features/course/api";
import { ChapterForm } from "@/features/course/ChapterForm";
import { Centered, ErrorText } from "@/ui/components";

export default function EditChapter() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const chapter = useChapter(id);
  const update = useUpdateChapter(id);

  if (chapter.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (chapter.isError) {
    return (
      <Centered>
        <ErrorText error={chapter.error} />
      </Centered>
    );
  }

  return (
    <ChapterForm
      initial={chapter.data}
      submitLabel="Save"
      busy={update.isPending}
      error={update.error}
      onSubmit={(values) => update.mutate(values, { onSuccess: () => router.back() })}
    />
  );
}
