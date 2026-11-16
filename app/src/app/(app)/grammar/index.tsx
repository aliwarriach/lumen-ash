import { router } from "expo-router";
import { ActivityIndicator, Pressable, RefreshControl, View } from "react-native";

import { EvidenceLine } from "@/features/grammar/EvidenceLine";
import {
  LEVEL_COLORS,
  LEVEL_LABELS,
  percent,
  usePatterns,
  useWeakPatterns,
  type PatternSummary,
  type WeakPattern,
} from "@/features/grammar/api";
import { useMistakeSummary } from "@/features/mistakes/api";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, ErrorText, SectionTitle } from "@/ui/components";
import { ArrowRight, ChevronRight, ICON } from "@/ui/icons";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

/** Where am I weak? The weakest patterns first, each with the answers behind it. */
export default function Grammar() {
  const styles = useStyles();
  const colors = useTheme();
  const weak = useWeakPatterns();
  const patterns = usePatterns();
  const summary = useMistakeSummary();
  const refreshing = weak.isRefetching || patterns.isRefetching;

  function refresh() {
    void weak.refetch();
    void patterns.refetch();
    void summary.refetch();
  }

  return (
    <FormScroll
      contentContainerStyle={styles.page}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
    >
      <View style={styles.actions}>
        <View style={styles.action}>
          <Button label="Log a mistake" onPress={() => router.push("/mistakes/new")} />
        </View>
        <View style={styles.action}>
          <Button
            label={summary.data ? `Mistake log (${summary.data.total})` : "Mistake log"}
            variant="secondary"
            onPress={() => router.push("/mistakes")}
          />
        </View>
      </View>

      <SectionTitle>Weakest right now</SectionTitle>
      {weak.isPending ? (
        <ActivityIndicator color={colors.primary} />
      ) : weak.isError ? (
        <ErrorText error={weak.error} />
      ) : weak.data.length === 0 ? (
        <Card>
          <Text style={styles.body}>No weak spots in the last 30 days.</Text>
          <Text style={styles.muted}>
            Practise a rule below (start with Kapitel 1), log mistakes from class, and answer your
            review cards: every checked answer counts towards the rule it tests.
          </Text>
        </Card>
      ) : (
        weak.data.map((w, i) => <WeakCard key={w.key} weak={w} rank={i + 1} />)
      )}

      <SectionTitle>All A1 grammar, in book order</SectionTitle>
      {patterns.isError && <ErrorText error={patterns.error} />}
      {patterns.data?.map((p, i, all) => (
        <View key={p.key} style={styles.group}>
          {(i === 0 || all[i - 1].book_chapter !== p.book_chapter) && (
            <Text style={styles.chapter}>Kapitel {p.book_chapter}</Text>
          )}
          <PatternRow pattern={p} />
        </View>
      ))}
    </FormScroll>
  );
}

function WeakCard({ weak, rank }: { weak: WeakPattern; rank: number }) {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <Card
      // The weakest rule is the one glass card on the page.
      glass={rank === 1}
      onPress={() => router.push({ pathname: "/grammar/[key]", params: { key: weak.key } })}
      label={`${rank}. ${weak.title}. ${weak.reason}`}
      hint="Rule, examples and practice"
    >
      <Text style={styles.title}>
        {rank}. {weak.title}
      </Text>
      <Text style={styles.reason}>{weak.reason}</Text>
      {weak.evidence.map((e, i) => (
        <EvidenceLine key={`${e.occurred_at}-${i}`} evidence={e} />
      ))}
      <View style={styles.more}>
        <Text style={styles.link}>Rule, examples and practice</Text>
        <ArrowRight size={ICON.inline} color={colors.primary} />
      </View>
    </Card>
  );
}

function PatternRow({ pattern: p }: { pattern: PatternSummary }) {
  const colors = useTheme();
  const styles = useStyles();
  const s = p.stats;
  const level = colors[LEVEL_COLORS[s.level]];
  return (
    <View style={styles.row}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${p.title}. ${s.attempts ? `${s.correct} of ${s.attempts} right` : "No answers yet"}. ${percent(s.accuracy)}`}
        onPress={() => router.push({ pathname: "/grammar/[key]", params: { key: p.key } })}
        android_ripple={{ color: colors.divider }}
        style={styles.rowOpen}
      >
        <View style={styles.rowText}>
          <Text style={styles.rowTitle}>{p.title}</Text>
          <Text style={styles.muted}>
            {s.attempts ? `${s.correct} of ${s.attempts} right` : "No answers yet"}
            {s.mistakes ? ` · ${s.mistakes} mistake${s.mistakes === 1 ? "" : "s"}` : ""}
          </Text>
          <View style={styles.levelRow}>
            <Text style={[styles.accuracy, { color: level }]}>{percent(s.accuracy)}</Text>
            {s.level !== "not_enough_data" && (
              <Text style={[styles.level, { color: level }]}>{LEVEL_LABELS[s.level]}</Text>
            )}
          </View>
        </View>
        <ChevronRight size={ICON.inline} color={colors.muted} />
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Practise ${p.title}`}
        onPress={() => router.push({ pathname: "/grammar/practice/[key]", params: { key: p.key } })}
        android_ripple={{ color: colors.onPrimary + "33" }}
        style={styles.practise}
      >
        <Text style={styles.practiseText}>Practise</Text>
      </Pressable>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  actions: { flexDirection: "row", gap: space.md },
  action: { flex: 1 },
  title: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  reason: { fontSize: 15, lineHeight: 22, fontWeight: "600", color: colors.danger },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  more: { flexDirection: "row", alignItems: "center", gap: space.xs, marginTop: space.xs },
  link: { fontSize: 15, lineHeight: 22, fontWeight: "700", color: colors.primary },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.flat,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    overflow: "hidden",
  },
  rowOpen: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    minHeight: TOUCH + 16,
    paddingVertical: space.md,
    paddingLeft: space.lg,
  },
  rowText: { flex: 1, gap: 2 },
  rowTitle: { fontSize: 16, lineHeight: 22, fontWeight: "700" },
  levelRow: { flexDirection: "row", alignItems: "baseline", gap: space.sm },
  accuracy: { fontSize: 15, lineHeight: 22, fontWeight: "800" },
  level: { fontSize: 13, lineHeight: 18, fontWeight: "600" },
  group: { gap: space.sm },
  chapter: { fontSize: 13, lineHeight: 18, fontWeight: "800", color: colors.muted, letterSpacing: 0.4, marginTop: space.sm, marginHorizontal: space.xs },
  practise: {
    minHeight: TOUCH,
    justifyContent: "center",
    marginHorizontal: space.md,
    paddingHorizontal: space.lg,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    overflow: "hidden",
  },
  practiseText: { color: colors.onPrimary, fontWeight: "800", fontSize: 14, lineHeight: 20 },
}));
