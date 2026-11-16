import { router } from "expo-router";

import { useCreateChapter } from "@/features/course/api";
import { ChapterForm } from "@/features/course/ChapterForm";

export default function NewChapter() {
  const create = useCreateChapter();
  return (
    <ChapterForm
      submitLabel="Add chapter"
      busy={create.isPending}
      error={create.error}
      onSubmit={(values) =>
        create.mutate(values, {
          onSuccess: (chapter) =>
            router.replace({ pathname: "/chapters/[id]", params: { id: chapter.id } }),
        })
      }
    />
  );
}
