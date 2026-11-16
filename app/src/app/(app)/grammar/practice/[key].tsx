import { Stack, router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator } from "react-native";

import {
  useAnswerPractice,
  usePracticeSet,
  useRefreshGrammar,
  type PatternKey,
} from "@/features/grammar/api";
import { PracticeSession } from "@/features/practice/Session";
import { Button, Centered, ErrorText } from "@/ui/components";

// Practice for one grammar pattern. Every first answer is stored and counts towards the pattern's
// accuracy on the Grammar page. Checked by plain rules: no AI.
export default function GrammarPractice() {
  const { key } = useLocalSearchParams<{ key: PatternKey }>();
  const set = usePracticeSet(key);
  const save = useAnswerPractice();
  const refresh = useRefreshGrammar();
  const [unsaved, setUnsaved] = useState(0);

  if (set.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (set.isError) {
    return (
      <Centered>
        <ErrorText error={set.error} />
        <Button label="Try again" variant="secondary" onPress={() => set.refetch()} />
      </Centered>
    );
  }
  return (
    <>
      <Stack.Screen options={{ title: set.data.title }} />
      <PracticeSession
        items={set.data.exercises}
        label={`Kapitel ${set.data.book_chapter}`}
        askTitle={set.data.title}
        unsaved={unsaved}
        countsTowards="Your answers count towards this rule on the Grammar page."
        onAnswered={(item, given) =>
          save.mutate({ exercise_id: item.id, given }, { onError: () => setUnsaved((n) => n + 1) })
        }
        onFinished={() => void refresh()}
        onBack={() => router.back()}
      />
    </>
  );
}
