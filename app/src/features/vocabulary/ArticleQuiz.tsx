import { useState } from "react";
import { Pressable, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";

import { ArticleButtons, type ButtonState } from "@/features/vocabulary/ArticleButtons";
import { GENDER, answerLine, pickRound, scoreLine, type ArticleFilter } from "@/features/vocabulary/articleRules";
import type { Article, Word } from "@/features/vocabulary/api";
import { Button } from "@/ui/components";
import { Celebration } from "@/ui/Celebration";
import { Glass } from "@/ui/glass";
import { RotateCcw } from "@/ui/icons";
import { useReduceMotion } from "@/ui/motion";
import { Text } from "@/ui/Text";
import { makeStyles, space, TOUCH, useTheme } from "@/ui/theme";

type QuizWord = Word & { article: Article };

/**
 * "Which article?": one of the learner's own nouns at a time, with der / die / das to pick from.
 * A round is up to ten nouns. Practice only: it does not change a word's review schedule (the
 * Review tab's cards do that).
 */
export function ArticleQuiz({ pool }: { pool: QuizWord[] }) {
  const styles = useStyles();
  const colors = useTheme();
  const [round, setRound] = useState(() => pickRound(pool));
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<Article | null>(null);
  const [score, setScore] = useState(0);
  const reduce = useReduceMotion();

  if (index >= round.length) {
    return (
      <Glass style={styles.card}>
        {score === round.length && <Celebration />}
        <Text style={styles.heading}>ROUND DONE</Text>
        <View style={styles.center}>
          <Text style={styles.big} accessibilityRole="header">
            {scoreLine(score, round.length)}
          </Text>
          <Text style={styles.meaning}>
            {score === round.length ? "Perfekt! Every article was right." : "Another round will pick different nouns."}
          </Text>
        </View>
        <Button
          label="Another round"
          icon={RotateCcw}
          onPress={() => {
            setRound(pickRound(pool));
            setIndex(0);
            setScore(0);
            setPicked(null);
          }}
        />
      </Glass>
    );
  }

  const word = round[index]!;
  const answered = picked !== null;
  const right = picked === word.article;

  const stateOf = (a: Article): ButtonState =>
    answered ? (a === word.article ? "right" : a === picked ? "wrong" : "idle") : "idle";

  function pick(a: Article) {
    if (answered) return;
    setPicked(a);
    if (a === word.article) setScore((n) => n + 1);
  }

  return (
    <Glass style={styles.card}>
      <View style={styles.head}>
        <Text style={styles.heading}>WHICH ARTICLE?</Text>
        <Text style={styles.heading}>
          {index + 1} of {round.length}
        </Text>
      </View>
      <View
        style={styles.center}
        accessible
        accessibilityLabel={`Which article goes with ${word.german}, ${word.meaning_en}?`}
      >
        <View style={styles.noun}>
          <Text style={[styles.big, { color: answered ? colors[word.article].text : colors.muted }]}>
            {answered ? word.article : "___"}
          </Text>
          <Text style={styles.big}>{word.german}</Text>
        </View>
        <Text style={styles.meaning}>{word.meaning_en}</Text>
      </View>

      <ArticleButtons label="Choose the article" state={stateOf} onPick={pick} />

      {answered && (
        <Animated.View
          entering={reduce ? undefined : FadeInDown.duration(160)}
          style={[styles.feedback, { backgroundColor: right ? colors.right.bg : colors.wrong.bg }]}
          accessibilityLiveRegion="polite"
        >
          <View style={styles.feedbackText}>
            <Text style={[styles.feedbackTitle, { color: right ? colors.right.fg : colors.wrong.fg }]}>
              {right ? "Richtig!" : "Not quite"}
            </Text>
            <Text style={styles.feedbackLine}>{answerLine(word)}</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setIndex((i) => i + 1);
              setPicked(null);
            }}
            android_ripple={{ color: colors.onPrimary + "33" }}
            style={styles.next}
          >
            <Text style={styles.nextText}>{index + 1 === round.length ? "Finish" : "Next"}</Text>
          </Pressable>
        </Animated.View>
      )}
    </Glass>
  );
}

/** One line that says what each article's color means, and why plurals are grey. */
export function ArticleKey() {
  const styles = useStyles();
  const colors = useTheme();
  const keys = [
    { article: "der", gender: GENDER.der, tone: colors.der },
    { article: "die", gender: GENDER.die, tone: colors.die },
    { article: "das", gender: GENDER.das, tone: colors.das },
  ] as const;
  return (
    <View style={styles.key}>
      <View style={styles.keyRow}>
        {keys.map(({ article, gender, tone }) => (
          <View key={article} style={styles.keyItem}>
            <View style={[styles.dot, { backgroundColor: tone.fill }]} />
            <Text style={[styles.keyArticle, { color: tone.text }]}>{article}</Text>
            <Text style={styles.keyGender}>{gender}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.keyGender}>Plurals always take die, so they stay grey.</Text>
    </View>
  );
}

/** The "All / der / die / das" filter under the colour key. Filled when on, outlined when off. */
export function ArticleFilterChips({
  value,
  onChange,
}: {
  value: ArticleFilter;
  onChange: (v: ArticleFilter) => void;
}) {
  const styles = useStyles();
  const colors = useTheme();
  const options: { id: ArticleFilter; label: string; fg: string; fill: string; onFill: string }[] = [
    { id: "all", label: "All", fg: colors.text, fill: colors.primaryContainer, onFill: colors.onPrimaryContainer },
    { id: "der", label: "der", fg: colors.der.text, fill: colors.der.fill, onFill: colors.der.onFill },
    { id: "die", label: "die", fg: colors.die.text, fill: colors.die.fill, onFill: colors.die.onFill },
    { id: "das", label: "das", fg: colors.das.text, fill: colors.das.fill, onFill: colors.das.onFill },
  ];
  return (
    <View style={styles.chips} accessibilityRole="radiogroup" accessibilityLabel="Filter by article">
      {options.map((o) => {
        const on = value === o.id;
        return (
          <Pressable
            key={o.id}
            accessibilityRole="radio"
            accessibilityState={{ checked: on }}
            onPress={() => onChange(o.id)}
            android_ripple={{ color: colors.divider }}
            style={[
              styles.chip,
              on ? { backgroundColor: o.fill, borderColor: o.fill } : { borderColor: colors.border },
            ]}
          >
            <Text style={[styles.chipText, { color: on ? o.onFill : o.fg }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  card: { padding: space.lg + space.xs, gap: space.lg },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  heading: { fontSize: 13, lineHeight: 18, fontWeight: "800", color: colors.muted, letterSpacing: 0.4 },
  center: { alignItems: "center", gap: space.xs, paddingVertical: space.sm },
  noun: { flexDirection: "row", alignItems: "baseline", gap: 10 },
  big: { fontSize: 34, lineHeight: 42, fontWeight: "800", textAlign: "center" },
  meaning: { fontSize: 16, lineHeight: 24, color: colors.muted, textAlign: "center" },
  feedback: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingVertical: 14,
    paddingHorizontal: space.lg,
    borderRadius: 18,
  },
  feedbackText: { flex: 1, gap: 2 },
  feedbackTitle: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  feedbackLine: { fontSize: 15, lineHeight: 22 },
  next: {
    minHeight: TOUCH,
    paddingHorizontal: 18,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  nextText: { fontSize: 16, lineHeight: 22, fontWeight: "800", color: colors.onPrimary },
  key: { gap: space.sm + 2, marginHorizontal: space.xs },
  keyRow: { flexDirection: "row", justifyContent: "space-between" },
  keyItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  keyArticle: { fontSize: 15, lineHeight: 22, fontWeight: "800" },
  keyGender: { fontSize: 14, lineHeight: 20, color: colors.muted },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  chip: {
    minHeight: TOUCH,
    paddingHorizontal: 18,
    borderRadius: 16,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  chipText: { fontSize: 16, lineHeight: 22, fontWeight: "800" },
}));
