import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator } from "react-native";

import { MistakeForm } from "@/features/mistakes/MistakeForm";
import { useMistake, useUpdateMistake } from "@/features/mistakes/api";
import { Centered, ErrorText } from "@/ui/components";

export default function EditMistake() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const mistake = useMistake(id);
  const update = useUpdateMistake(id);

  if (mistake.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (mistake.isError) {
    return (
      <Centered>
        <ErrorText error={mistake.error} />
      </Centered>
    );
  }

  return (
    <MistakeForm
      initial={mistake.data}
      submitLabel="Save"
      busy={update.isPending}
      error={update.error}
      onSubmit={(values) => update.mutate(values, { onSuccess: () => router.back() })}
    />
  );
}
