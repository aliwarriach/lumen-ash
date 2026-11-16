import { useState } from "react";
import { Pressable, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";

import {
  blankProblem,
  fillFrame,
  isCorrect,
  nearMiss,
  scrambleTiles,
  shownAnswer,
  shuffle,
  type PracticeItem,
} from "@/features/practice/check";
import { AskCommunityButton } from "@/features/community/AskCommunity";
import { aboutExercise } from "@/features/community/ask";
import { Celebration } from "@/ui/Celebration";
import { Button, Card, Field, IconLabel, ProgressBar, TextLink } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Check, ICON, Lightbulb, X } from "@/ui/icons";
import { useReduceMotion } from "@/ui/motion";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

type Props = {
  items: PracticeItem[];
  /** Shown above the progress bar, e.g. "Kapitel 4". */
  label?: string;
  /** Names the round on an "Ask the Community" card, e.g. the rule's or the lesson's title. */
  askTitle?: string;
  /** Keep the given order instead of shuffling (sentence lessons go from easy to hard). */
  keepOrder?: boolean;
  /** Every first answer, e.g. to store it. */
  onAnswered?: (item: PracticeItem, given: string, correct: boolean) => void;
  /** When a round ends. */
  onFinished?: (right: number, total: number) => void;
  /** Answers that could not be saved, shown on the score card. */
  unsaved?: number;
  /** What the score card says the round counts towards. */
  countsTowards: string;
  onBack: () => void;
};

/**
 * One practice round: the exercises one at a time, a hint before answering, the reason after, and
 * a score at the end. Used by grammar practice and the sentence lessons. Checked by plain rules.
 */
export function PracticeSession({
  items,
  label,
  askTitle,
  keepOrder = false,
  onAnswered,
  onFinished,
  unsaved = 0,
  countsTowards,
  onBack,
}: Props) {
  const styles = useStyles();
  const [order, setOrder] = useState(() => (keepOrder ? items : shuffle(items)));
  const [round, setRound] = useState(0);
  const [index, setIndex] = useState(0);
  const [right, setRight] = useState(0);

  function answered(item: PracticeItem, given: string, correct: boolean) {
    if (correct) setRight((n) => n + 1);
    onAnswered?.(item, given, correct);
  }

  function next() {
    if (index + 1 >= order.length) onFinished?.(right, order.length);
    setIndex((i) => i + 1);
  }

  function again() {
    setOrder(keepOrder ? items : shuffle(items));
    setRound((r) => r + 1);
    setIndex(0);
    setRight(0);
  }

  const done = index >= order.length;
  return (
    <FormScroll contentContainerStyle={styles.page}>
      <View style={styles.progressRow}>
        <Text style={styles.muted}>
          {done ? "Finished" : `${index + 1} of ${order.length}`}
          {label ? ` · ${label}` : ""}
        </Text>
        <Text style={styles.muted}>{right} right</Text>
      </View>
      <ProgressBar value={Math.min(index, order.length) / order.length} label="Practice progress" />

      {done ? (
        <Summary
          right={right}
          total={order.length}
          unsaved={unsaved}
          countsTowards={countsTowards}
          onAgain={again}
          onBack={onBack}
        />
      ) : (
        <ItemView
          key={`${round}-${order[index].id}`}
          item={order[index]}
          where={`${askTitle ?? label ?? "Practice"} · ${index + 1} of ${order.length}`}
          last={index + 1 === order.length}
          onAnswered={answered}
          onNext={next}
        />
      )}
    </FormScroll>
  );
}

const KIND_LABELS: Record<PracticeItem["kind"], string> = {
  choice: "Choose the right answer",
  fill: "Type the missing word",
  order: "Put the words in order",
  bank: "Build the sentence (some words don't belong)",
  frame: "Write about yourself",
};

function ItemView({
  item,
  where,
  last,
  onAnswered,
  onNext,
}: {
  item: PracticeItem;
  /** "Perfekt mit haben · 3 of 10", for an "Ask the Community" card. */
  where: string;
  last: boolean;
  onAnswered: (item: PracticeItem, given: string, correct: boolean) => void;
  onNext: () => void;
}) {
  const styles = useStyles();
  const colors = useTheme();
  const reduce = useReduceMotion();
  const [verdict, setVerdict] = useState<{ given: string; correct: boolean } | null>(null);
  const [showHint, setShowHint] = useState(false);
  const checked = verdict !== null;

  function check(given: string, correct: boolean) {
    if (checked) return;
    setVerdict({ given, correct });
    onAnswered(item, given, correct);
  }

  const tip = verdict && !verdict.correct && item.kind !== "frame" ? nearMiss(item, verdict.given) : null;

  return (
    <>
      <Card glass>
        <Text style={styles.kind}>{KIND_LABELS[item.kind]}</Text>
        {item.kind === "order" || item.kind === "bank" ? (
          <>
            <Text style={styles.muted}>Say it in German:</Text>
            <Text style={styles.prompt}>{item.prompt}</Text>
          </>
        ) : (
          <>
            <Text style={styles.prompt}>{item.prompt}</Text>
            {item.english ? <Text style={styles.muted}>{item.english}</Text> : null}
          </>
        )}
      </Card>

      <AskCommunityButton
        attachment={() => aboutExercise(where, KIND_LABELS[item.kind], item, verdict?.given)}
      />

      {item.kind === "choice" && <ChoiceView item={item} verdict={verdict} onCheck={check} />}
      {item.kind === "fill" && <FillView item={item} checked={checked} onCheck={check} />}
      {(item.kind === "order" || item.kind === "bank") && (
        <TilesView item={item} verdict={verdict} onCheck={check} />
      )}
      {item.kind === "frame" && <FrameView item={item} checked={checked} onCheck={check} />}

      {!checked &&
        (showHint ? (
          <View style={styles.hint}>
            <IconLabel icon={Lightbulb} color={colors.amber.fg} style={styles.hintText}>
              {item.hint}
            </IconLabel>
          </View>
        ) : (
          <TextLink label="Show a hint" icon={Lightbulb} onPress={() => setShowHint(true)} />
        ))}

      {verdict && (
        <Animated.View
          entering={reduce ? undefined : FadeInDown.duration(160)}
          accessibilityLiveRegion="polite"
          style={[styles.verdictCard, { backgroundColor: verdict.correct ? colors.right.bg : colors.wrong.bg }]}
        >
          <IconLabel
            icon={verdict.correct ? Check : X}
            size={ICON.bar}
            color={verdict.correct ? colors.right.fg : colors.wrong.fg}
            style={[styles.verdict, { color: verdict.correct ? colors.right.fg : colors.wrong.fg }]}
          >
            {verdict.correct ? "Richtig!" : "Not quite"}
          </IconLabel>
          {item.kind === "frame" ? (
            <>
              <Text style={styles.body}>
                Your text: <Text style={styles.answer}>{verdict.given}</Text>
              </Text>
              <Text style={styles.muted}>Example: {item.answers[0]}</Text>
            </>
          ) : (
            !verdict.correct && (
              <Text style={styles.body}>
                The answer: <Text style={styles.answer}>{shownAnswer(item)}</Text>
              </Text>
            )
          )}
          {tip && <Text style={styles.body}>{tip}</Text>}
          <Text style={styles.muted}>{item.why}</Text>
          <Button label={last ? "See my score" : "Next"} onPress={onNext} />
        </Animated.View>
      )}
    </>
  );
}

type CheckFn = (given: string, correct: boolean) => void;

function ChoiceView({
  item,
  verdict,
  onCheck,
}: {
  item: PracticeItem;
  verdict: { given: string; correct: boolean } | null;
  onCheck: CheckFn;
}) {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <View style={styles.options}>
      {item.options.map((o) => {
        const isAnswer = verdict !== null && o === item.answers[0];
        const isWrongPick = verdict !== null && o === verdict.given && !verdict.correct;
        return (
          <Pressable
            key={o}
            accessibilityRole="button"
            accessibilityState={{ disabled: verdict !== null, selected: o === verdict?.given }}
            disabled={verdict !== null}
            onPress={() => onCheck(o, isCorrect(item, o))}
            android_ripple={{ color: colors.divider }}
            style={[styles.option, isAnswer && styles.right, isWrongPick && styles.wrong]}
          >
            <Text style={styles.optionText}>{o}</Text>
            {isAnswer && <Check size={ICON.inline} strokeWidth={3} color={colors.right.fg} />}
            {isWrongPick && <X size={ICON.inline} strokeWidth={3} color={colors.wrong.fg} />}
          </Pressable>
        );
      })}
    </View>
  );
}

function FillView({ item, checked, onCheck }: { item: PracticeItem; checked: boolean; onCheck: CheckFn }) {
  const [typed, setTyped] = useState("");
  const submit = () => typed.trim() && onCheck(typed, isCorrect(item, typed));
  return (
    <>
      <Field
        label="Your answer"
        value={typed}
        onChangeText={setTyped}
        autoCapitalize="none"
        autoCorrect={false}
        editable={!checked}
        onSubmitEditing={submit}
        returnKeyType="done"
      />
      {!checked && <Button label="Check" disabled={!typed.trim()} onPress={submit} />}
    </>
  );
}

function TilesView({
  item,
  verdict,
  onCheck,
}: {
  item: PracticeItem;
  verdict: { given: string; correct: boolean } | null;
  onCheck: CheckFn;
}) {
  const styles = useStyles();
  const colors = useTheme();
  const [tiles] = useState(() => scrambleTiles(item));
  const [picked, setPicked] = useState<number[]>([]); // indices into `tiles`, in answer order
  const checked = verdict !== null;
  // A word bank has extra tiles, so the sentence may be done before every tile is used.
  const ready = item.kind === "bank" ? picked.length > 0 : picked.length === tiles.length;
  const sentence = picked.map((t) => tiles[t]).join(" ");

  return (
    <>
      <View style={[styles.answerLine, verdict && (verdict.correct ? styles.right : styles.wrong)]}>
        {picked.length === 0 ? (
          <Text style={styles.muted}>Tap the words below in the right order.</Text>
        ) : (
          picked.map((t) => (
            <Pressable
              key={t}
              accessibilityRole="button"
              accessibilityLabel={`Remove ${tiles[t]}`}
              disabled={checked}
              onPress={() => setPicked((p) => p.filter((x) => x !== t))}
              android_ripple={{ color: colors.divider }}
              style={[styles.tile, styles.tileChosen]}
            >
              <Text style={styles.tileText}>{tiles[t]}</Text>
            </Pressable>
          ))
        )}
        {ready && <Text style={styles.tileText}>{item.end}</Text>}
      </View>
      {!checked && (
        <View style={styles.pool}>
          {tiles.map((t, i) =>
            picked.includes(i) ? null : (
              <Pressable
                key={i}
                accessibilityRole="button"
                onPress={() => setPicked((p) => [...p, i])}
                android_ripple={{ color: colors.divider }}
                style={styles.tile}
              >
                <Text style={styles.tileText}>{t}</Text>
              </Pressable>
            ),
          )}
        </View>
      )}
      {!checked && (
        <Button label="Check" disabled={!ready} onPress={() => onCheck(sentence, isCorrect(item, sentence))} />
      )}
    </>
  );
}

function FrameView({ item, checked, onCheck }: { item: PracticeItem; checked: boolean; onCheck: CheckFn }) {
  const styles = useStyles();
  const blanks = item.blanks ?? [];
  const [values, setValues] = useState<string[]>(() => blanks.map(() => ""));
  const [problems, setProblems] = useState<(string | null)[]>([]);

  function submit() {
    const found = blanks.map((b, i) => blankProblem(b, values[i]));
    setProblems(found);
    // A frame is about writing your own words: a gap that breaks a rule is shown, and can be fixed
    // before it is checked. Only a complete, rule-following text counts as done.
    if (found.every((p) => p === null)) onCheck(fillFrame(item.prompt, values), true);
  }

  return (
    <>
      <Text style={styles.preview}>{fillFrame(item.prompt, values)}</Text>
      {blanks.map((b, i) => (
        <View key={i} style={styles.blank}>
          <Field
            label={capitaliseFirst(b.label)}
            value={values[i]}
            onChangeText={(t) => setValues((v) => v.map((x, j) => (j === i ? t : x)))}
            placeholder={`e.g. ${b.example}`}
            autoCapitalize="none"
            autoCorrect={false}
            editable={!checked}
          />
          {problems[i] && <Text style={styles.problem}>{problems[i]}</Text>}
        </View>
      ))}
      {!checked && (
        <Button label="Check" disabled={values.some((v) => !v.trim())} onPress={submit} />
      )}
    </>
  );
}

const capitaliseFirst = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function Summary({
  right,
  total,
  unsaved,
  countsTowards,
  onAgain,
  onBack,
}: {
  right: number;
  total: number;
  unsaved: number;
  countsTowards: string;
  onAgain: () => void;
  onBack: () => void;
}) {
  const styles = useStyles();
  const share = right / total;
  const message =
    share >= 0.9
      ? "Excellent!"
      : share >= 0.7
        ? "Good. One more round will make it stick."
        : "This one needs practice. Look at the hints, then try another round.";
  return (
    <Card glass>
      {share >= 0.9 && <Celebration />}
      <Text style={styles.score} accessibilityRole="header">
        {right} of {total} right
      </Text>
      <Text style={styles.body}>{message}</Text>
      <Text style={styles.muted}>{countsTowards}</Text>
      {unsaved > 0 && (
        <Text style={styles.warning}>
          {unsaved} answer{unsaved === 1 ? " wasn't" : "s weren't"} saved (no connection). They
          still counted in this score.
        </Text>
      )}
      <Button label="Practise again" onPress={onAgain} />
      <Button label="Back" variant="secondary" onPress={onBack} />
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.xl, gap: space.md },
  progressRow: { flexDirection: "row", justifyContent: "space-between" },
  kind: { fontSize: 13, lineHeight: 18, fontWeight: "800", color: colors.muted, letterSpacing: 0.4, textTransform: "uppercase" },
  prompt: { fontSize: 22, lineHeight: 30, fontWeight: "700" },
  preview: { fontSize: 17, lineHeight: 24, fontStyle: "italic" },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  warning: { fontSize: 14, lineHeight: 20, color: colors.warning },
  problem: { fontSize: 14, lineHeight: 20, color: colors.danger },
  hint: { backgroundColor: colors.amber.bg, padding: space.lg, borderRadius: 18 },
  hintText: { fontSize: 15, lineHeight: 22, color: colors.text },
  options: { gap: space.sm },
  option: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space.md,
    minHeight: TOUCH + 8,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    borderRadius: 18,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    overflow: "hidden",
  },
  right: { borderColor: colors.right.edge, backgroundColor: colors.right.bg },
  wrong: { borderColor: colors.wrong.edge, backgroundColor: colors.wrong.bg },
  optionText: { flexShrink: 1, fontSize: 17, lineHeight: 24, fontWeight: "600" },
  answerLine: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: space.sm,
    minHeight: 64,
    padding: space.sm,
    borderRadius: 18,
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  pool: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  tile: {
    minHeight: TOUCH,
    justifyContent: "center",
    paddingHorizontal: space.lg,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.primary,
    backgroundColor: colors.surface,
    overflow: "hidden",
  },
  tileChosen: { backgroundColor: colors.primaryContainer },
  tileText: { fontSize: 17, lineHeight: 24, fontWeight: "600" },
  blank: { gap: space.xs },
  verdictCard: { gap: space.md, padding: space.lg + space.xs, borderRadius: 24 },
  verdict: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  answer: { fontWeight: "800" },
  score: { fontSize: 26, lineHeight: 34, fontWeight: "800" },
}));
