import { Stack, router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator } from "react-native";

import { PracticeSession } from "@/features/practice/Session";
import { useLesson, useSaveLessonResult } from "@/features/sentences/api";
import { Text } from "@/ui/Text";
import { Button, Centered, ErrorText } from "@/ui/components";
import { makeStyles, space } from "@/ui/theme";

// One sentence lesson, from tiles to guided writing, in that order (easiest first). The score of
// each round is saved. Checked by plain rules: no AI.
export default function SentenceLesson() {
  const styles = useStyles();
  const { id } = useLocalSearchParams<{ id: string }>();
  const lesson = useLesson(id);
  const save = useSaveLessonResult(id);
  const [unsaved, setUnsaved] = useState(0);

  if (lesson.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (lesson.isError) {
    return (
      <Centered>
        <ErrorText error={lesson.error} />
        <Button label="Try again" variant="secondary" onPress={() => lesson.refetch()} />
      </Centered>
    );
  }
  const l = lesson.data;
  if (l.exercises.length === 0) {
    return (
      <Centered>
        <Stack.Screen options={{ title: l.title }} />
        <Text style={styles.empty}>
          No sentences yet. Add words from the dictionary on the Words tab: words that have an
          example sentence turn into exercises here.
        </Text>
        <Button label="Back" variant="secondary" onPress={() => router.back()} />
      </Centered>
    );
  }
  return (
    <>
      <Stack.Screen options={{ title: l.title }} />
      <PracticeSession
        items={l.exercises}
        label={l.book_chapter ? `Kapitel ${l.book_chapter} · ${l.topic}` : l.topic}
        askTitle={l.title}
        keepOrder={l.book_chapter !== null}
        unsaved={unsaved}
        countsTowards="Your best score shows on the Write tab."
        onFinished={(right, total) =>
          save.mutate({ right, total }, { onError: () => setUnsaved((n) => n + 1) })
        }
        onBack={() => router.back()}
      />
    </>
  );
}

const useStyles = makeStyles((colors) => ({
  empty: { color: colors.muted, textAlign: "center", paddingHorizontal: space.lg },
}));
