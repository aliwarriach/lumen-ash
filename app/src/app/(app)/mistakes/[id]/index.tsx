import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, View } from "react-native";

import { useChapters } from "@/features/course/api";
import { CATEGORY_LABELS } from "@/features/grammar/api";
import { useMistakeStyles, shortDate } from "@/features/mistakes/MistakeRow";
import { useDeleteMistake, useMistake } from "@/features/mistakes/api";
import { headword } from "@/features/vocabulary/api";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, Pill, SectionTitle, TextLink } from "@/ui/components";
import { ChevronRight, ICON } from "@/ui/icons";
import { makeStyles, space, useTheme } from "@/ui/theme";

export default function MistakeDetail() {
  const styles = useStyles();
  const colors = useTheme();
  const mistakeStyles = useMistakeStyles();
  const { id } = useLocalSearchParams<{ id: string }>();
  const mistake = useMistake(id);
  const chapters = useChapters();
  const remove = useDeleteMistake(id);

  if (mistake.isPending) {
    return (
      <Centered>
        <ActivityIndicator color={colors.primary} />
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

  const m = mistake.data;
  const chapter = chapters.data?.find((c) => c.id === m.chapter_id);
  const retry = m.retry;

  function confirmDelete() {
    Alert.alert("Delete this mistake?", "Its review card and grammar evidence go too.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => remove.mutate(undefined, { onSuccess: () => router.back() }),
      },
    ]);
  }

  return (
    <FormScroll contentContainerStyle={styles.page}>
      <Card glass>
        <View style={styles.pills}>
          <Pill label={CATEGORY_LABELS[m.category]} accent={{ fg: colors.muted, bg: colors.well }} />
          <Text style={styles.muted}>{shortDate(m.created_at)}</Text>
        </View>
        <Text style={[mistakeStyles.wrong, styles.big]}>{m.wrong}</Text>
        <Text style={[mistakeStyles.correct, styles.big]}>{m.correct}</Text>
        {m.explanation && <Text style={styles.body}>{m.explanation}</Text>}
      </Card>

      {m.repeat_of && (
        <Card>
          <Pill label="Repeat mistake" accent={colors.amber} />
          <Text style={styles.body}>{m.repeat_of.reason}</Text>
          <TextLink
            label={`Earlier, on ${shortDate(m.repeat_of.created_at)}: ${m.repeat_of.wrong}`}
            onPress={() => router.push({ pathname: "/mistakes/[id]", params: { id: m.repeat_of!.id } })}
          />
        </Card>
      )}

      {m.pattern_key && (
        <Card
          onPress={() => router.push({ pathname: "/grammar/[key]", params: { key: m.pattern_key! } })}
          label={`Grammar rule: ${m.pattern_title}`}
        >
          <SectionTitle>Grammar rule</SectionTitle>
          <View style={styles.ruleRow}>
            <Text style={styles.link}>{m.pattern_title}</Text>
            <ChevronRight size={ICON.inline} color={colors.muted} />
          </View>
        </Card>
      )}

      {m.words.length > 0 && (
        <Card>
          <SectionTitle>Words</SectionTitle>
          {m.words.map((w) => (
            <TextLink
              key={w.id}
              label={headword(w)}
              onPress={() => router.push({ pathname: "/words/[id]", params: { id: w.id } })}
            />
          ))}
        </Card>
      )}

      {retry && (
        <Card>
          <SectionTitle>Practice</SectionTitle>
          <Text style={styles.body}>
            {retry.retries === 0
              ? "Not retried yet. It's in your review queue."
              : `Retried ${retry.retries} time${retry.retries === 1 ? "" : "s"}; last time ${
                  retry.last_correct ? "you got it right" : "it was still wrong"
                }.`}
          </Text>
          {retry.retries > 0 && (
            <Text style={styles.muted}>Next retry: {shortDate(retry.due)}</Text>
          )}
        </Card>
      )}

      <Text style={styles.muted}>
        {[chapter && `Kapitel ${chapter.number}`, m.source].filter(Boolean).join(" · ")}
      </Text>

      <Button
        label="Edit"
        variant="secondary"
        onPress={() => router.push({ pathname: "/mistakes/[id]/edit", params: { id: m.id } })}
      />
      <Button label="Delete" variant="danger" busy={remove.isPending} onPress={confirmDelete} />
    </FormScroll>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  pills: { flexDirection: "row", alignItems: "center", gap: space.md },
  big: { fontSize: 22, lineHeight: 30 },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  ruleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  link: { fontSize: 16, lineHeight: 24, color: colors.primary, fontWeight: "700" },
}));
