import { Stack, router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator } from "react-native";

import { useChapters } from "@/features/course/api";
import { EvidenceLine } from "@/features/grammar/EvidenceLine";
import {
  CATEGORY_LABELS,
  LEVEL_COLORS,
  LEVEL_LABELS,
  describeStats,
  usePattern,
  useSetPatternChapters,
  type PatternKey,
} from "@/features/grammar/api";
import { AskCommunityButton } from "@/features/community/AskCommunity";
import { aboutGrammar } from "@/features/community/ask";
import { useMistakeStyles } from "@/features/mistakes/MistakeRow";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, MultiChips, Pill, SectionTitle } from "@/ui/components";
import { makeStyles, space, useTheme } from "@/ui/theme";

export default function PatternDetail() {
  const colors = useTheme();
  const styles = useStyles();
  const mistakeStyles = useMistakeStyles();
  const { key } = useLocalSearchParams<{ key: PatternKey }>();
  const pattern = usePattern(key);
  const chapters = useChapters();
  const setChapters = useSetPatternChapters(key);

  if (pattern.isPending) {
    return (
      <Centered>
        <ActivityIndicator color={colors.primary} />
      </Centered>
    );
  }
  if (pattern.isError) {
    return (
      <Centered>
        <ErrorText error={pattern.error} />
      </Centered>
    );
  }

  const p = pattern.data;
  const s = p.stats;

  function toggleChapter(id: string) {
    const next = p.chapter_ids.includes(id)
      ? p.chapter_ids.filter((c) => c !== id)
      : [...p.chapter_ids, id];
    setChapters.mutate(next);
  }

  return (
    <>
      <Stack.Screen options={{ title: p.title }} />
      <FormScroll contentContainerStyle={styles.page}>
        <Card glass>
          <Pill label={CATEGORY_LABELS[p.category]} accent={{ fg: colors.muted, bg: colors.well }} />
          <Text style={styles.title} accessibilityRole="header">
            {p.title}
          </Text>
          <Text style={[styles.level, { color: colors[LEVEL_COLORS[s.level]] }]}>
            {LEVEL_LABELS[s.level]}
          </Text>
          <Text style={styles.body}>{describeStats(s)}</Text>
          {s.mistakes > 0 && (
            <Text style={styles.muted}>
              {s.mistakes} logged mistake{s.mistakes === 1 ? "" : "s"}
              {s.repeats ? `, ${s.repeats} of them repeats` : ""}.
            </Text>
          )}
        </Card>

        <AskCommunityButton
          attachment={() =>
            aboutGrammar({ title: p.title, category: CATEGORY_LABELS[p.category], explanation: p.explanation })
          }
        />

        <Button
          label={`Practise this rule (${p.exercise_count} exercises)`}
          onPress={() => router.push({ pathname: "/grammar/practice/[key]", params: { key: p.key } })}
        />

        <Card>
          <SectionTitle>The rule</SectionTitle>
          <Text style={styles.body}>{p.explanation}</Text>
          <SectionTitle>Examples</SectionTitle>
          {p.examples.map((e) => (
            <Text key={e.german} style={styles.body}>
              {e.german} <Text style={styles.muted}>{e.english}</Text>
            </Text>
          ))}
        </Card>

        <Card>
          <SectionTitle>Common mistakes</SectionTitle>
          {p.common_mistakes.map((m) => (
            <Text key={m.wrong} style={styles.mistake}>
              <Text style={mistakeStyles.wrong}>{m.wrong}</Text>
              {"\n"}
              <Text style={mistakeStyles.correct}>→ {m.correct}</Text>
              {"\n"}
              <Text style={styles.muted}>{m.why}</Text>
            </Text>
          ))}
        </Card>

        {chapters.data && chapters.data.length > 0 && (
          <Card>
            <MultiChips
              label="In my course"
              options={chapters.data.map((c) => ({ value: c.id, label: `Kapitel ${c.number}` }))}
              selected={p.chapter_ids}
              onToggle={toggleChapter}
            />
            {setChapters.isError && <ErrorText error={setChapters.error} />}
          </Card>
        )}

        <Card>
          <SectionTitle>My recent answers</SectionTitle>
          {p.evidence.length === 0 ? (
            <Text style={styles.muted}>Nothing yet for this rule.</Text>
          ) : (
            p.evidence.map((e, i) => <EvidenceLine key={`${e.occurred_at}-${i}`} evidence={e} />)
          )}
        </Card>

        <Button
          label="Log a mistake with this rule"
          onPress={() => router.push({ pathname: "/mistakes/new", params: { patternKey: p.key } })}
        />
        {s.mistakes > 0 && (
          <Button
            label="See my mistakes"
            variant="secondary"
            onPress={() => router.push({ pathname: "/mistakes", params: { patternKey: p.key } })}
          />
        )}
        <Text style={styles.note}>
          Rules and examples are a study aid. If your book or teacher says something different,
          follow them.
        </Text>
      </FormScroll>
    </>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  title: { fontSize: 26, lineHeight: 34, fontWeight: "800" },
  level: { fontSize: 15, lineHeight: 22, fontWeight: "800" },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  mistake: { fontSize: 16, lineHeight: 24, marginBottom: space.xs },
  note: { fontSize: 13, lineHeight: 18, color: colors.muted, marginHorizontal: space.xs },
}));
