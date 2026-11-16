import { Stack, router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, FlatList, View } from "react-native";

import { CATEGORY_LABELS, type MistakeCategory, type PatternKey } from "@/features/grammar/api";
import { MistakeRow } from "@/features/mistakes/MistakeRow";
import { useMistakeSummary, useMistakes } from "@/features/mistakes/api";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, Chips, ErrorText } from "@/ui/components";
import { useBottomInset } from "@/ui/FormScroll";
import { makeStyles, space, useTheme } from "@/ui/theme";

type Filter = MistakeCategory | "all" | "repeats";

/** The mistake log, filterable by kind of mistake. Opened with ?patternKey= from a rule page. */
export default function MistakeLog() {
  const styles = useStyles();
  const colors = useTheme();
  const bottom = useBottomInset();
  const { patternKey } = useLocalSearchParams<{ patternKey?: PatternKey }>();
  const [filter, setFilter] = useState<Filter>("all");
  const summary = useMistakeSummary();
  const mistakes = useMistakes({
    patternKey,
    category: filter !== "all" && filter !== "repeats" ? filter : undefined,
    repeatsOnly: filter === "repeats",
  });
  const s = summary.data;
  const title = patternKey
    ? (s?.by_pattern.find((p) => p.key === patternKey)?.title ?? "Mistakes")
    : "Mistake log";

  const options: { value: Filter; label: string }[] = [
    { value: "all", label: "All" },
    ...(s?.repeats ? [{ value: "repeats" as const, label: `Repeats (${s.repeats})` }] : []),
    ...(patternKey
      ? []
      : (s?.by_category ?? []).map((c) => ({
          value: c.category,
          label: `${CATEGORY_LABELS[c.category]} (${c.total})`,
        }))),
  ];

  return (
    <>
      <Stack.Screen options={{ title }} />
      <FlatList
        data={mistakes.data}
        keyExtractor={(m) => m.id}
        contentContainerStyle={[styles.list, { paddingBottom: space.xl + bottom }]}
        ListHeaderComponent={
          <View style={styles.header}>
            {s && s.total > 0 && (
              <Text style={styles.muted}>
                {s.total} mistake{s.total === 1 ? "" : "s"} logged, {s.last_30_days} in the last
                30 days. Each one comes back in your reviews until you can fix it.
              </Text>
            )}
            {options.length > 1 && <Chips options={options} selected={filter} onSelect={setFilter} />}
            <Button
              label="Log a mistake"
              onPress={() =>
                router.push({ pathname: "/mistakes/new", params: patternKey ? { patternKey } : {} })
              }
            />
          </View>
        }
        renderItem={({ item }) => <MistakeRow mistake={item} />}
        ListEmptyComponent={
          mistakes.isPending ? (
            <Centered>
              <ActivityIndicator color={colors.primary} />
            </Centered>
          ) : mistakes.isError ? (
            <ErrorText error={mistakes.error} />
          ) : (
            <Card>
              <Text style={styles.muted}>
                No mistakes here yet. When your teacher corrects you, or you spot an error in your
                homework, log it: the app turns it into practice and tracks the rule behind it.
              </Text>
            </Card>
          )
        }
      />
    </>
  );
}

const useStyles = makeStyles((colors) => ({
  list: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.sm },
  header: { gap: space.md, marginBottom: space.sm },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
}));
