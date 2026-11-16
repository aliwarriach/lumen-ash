import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, View } from "react-native";

import { useAiQuota } from "@/features/ai/api";
import {
  TASK_IDEAS,
  useCheckWriting,
  useCreateTask,
  useFlagged,
  useTasks,
  type CheckResult,
  type Correction,
} from "@/features/coach/api";
import { CheckResultView } from "@/features/coach/CheckResultView";
import { useLessons, type LessonSummary } from "@/features/sentences/api";
import { Button, Card, Chips, ErrorText, Field, IconLabel, Pill } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Check, ChevronDown, ChevronRight, ChevronUp, ICON } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, space, TOUCH, useTheme } from "@/ui/theme";

const FREE = "free";

/**
 * Sentences: build German sentences step by step, one lesson per chapter (tiles, a word bank,
 * choices, one missing word, then a guided text about yourself), plus sentences made from the
 * learner's own words. Checked by plain rules. Free writing with the AI check is optional, below.
 */
export default function Sentences() {
  const colors = useTheme();
  const styles = useStyles();
  const lessons = useLessons();
  const [freeOpen, setFreeOpen] = useState(false);
  // The lesson to do next (the first with exercises you have not started) is the one glass card.
  const next = lessons.data?.find((l) => l.exercise_count > 0 && l.best_right === null)?.id;

  return (
    <FormScroll contentContainerStyle={styles.page}>
      <Text style={styles.intro}>
        Build sentences step by step: tap the words into order, choose, fill a gap, then write a
        few lines about yourself with a frame to help.
      </Text>
      {lessons.isPending && <ActivityIndicator color={colors.primary} />}
      {lessons.isError && <ErrorText error={lessons.error} />}
      {lessons.data?.map((l) => <LessonRow key={l.id} lesson={l} next={l.id === next} />)}

      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: freeOpen }}
        onPress={() => setFreeOpen((o) => !o)}
        android_ripple={{ color: colors.divider }}
        style={styles.linkTarget}
      >
        <IconLabel trailing icon={freeOpen ? ChevronUp : ChevronDown} color={colors.primary} style={styles.link}>
          Free writing, checked by AI (optional)
        </IconLabel>
      </Pressable>
      {freeOpen && <FreeWriting />}
    </FormScroll>
  );
}

function LessonRow({ lesson: l, next }: { lesson: LessonSummary; next: boolean }) {
  const styles = useStyles();
  const colors = useTheme();
  const mine = l.book_chapter === null;
  const empty = l.exercise_count === 0;
  const started = l.best_right !== null;
  const score = started ? `Best: ${l.best_right} of ${l.exercise_count}` : "Not started";
  const where = mine ? "Your words" : `Kapitel ${l.book_chapter}`;
  return (
    <Card
      glass={next}
      onPress={() => router.push({ pathname: "/sentences/[id]", params: { id: l.id } })}
      label={`${where}, ${l.title}. ${l.topic}. ${empty ? "Add words first" : `${l.exercise_count} exercises. ${score}`}`}
    >
      <View style={styles.lessonTop}>
        <Text style={styles.chapter}>{where}</Text>
        {next && <Pill label="Up next" accent={{ fg: colors.onPrimaryContainer, bg: colors.primaryContainer }} />}
      </View>
      <View style={styles.lessonRow}>
        <View style={styles.lessonText}>
          <Text style={styles.lessonTitle}>{l.title}</Text>
          <Text style={styles.muted}>{l.topic}</Text>
        </View>
        <ChevronRight size={ICON.bar} color={colors.muted} />
      </View>
      <View style={styles.lessonTop}>
        <Text style={styles.muted}>{empty ? "Add words first" : `${l.exercise_count} exercises`}</Text>
        {!empty &&
          (started ? (
            <Pill label={score} accent={colors.green} icon={Check} />
          ) : (
            <Text style={styles.muted}>{score}</Text>
          ))}
      </View>
    </Card>
  );
}

function FreeWriting() {
  const styles = useStyles();
  const tasks = useTasks();
  const createTask = useCreateTask();
  const check = useCheckWriting();
  const quota = useAiQuota();
  const flagged = useFlagged();
  const [text, setText] = useState("");
  const [taskId, setTaskId] = useState<string>(FREE);
  const [result, setResult] = useState<CheckResult | null>(null);

  const left = quota.data?.features.find((f) => f.feature === "sentence_coach");
  const task = tasks.data?.find((t) => t.id === taskId);
  const ideas = TASK_IDEAS.filter((i) => !tasks.data?.some((t) => t.prompt === i.prompt));

  function submit() {
    check.mutate(
      { text: text.trim(), task_id: taskId === FREE ? null : taskId },
      { onSuccess: setResult },
    );
  }

  // A decision changes one correction: keep the rest of the result as it is.
  function updated(c: Correction) {
    setResult((r) => r && { ...r, corrections: r.corrections.map((x) => (x.id === c.id ? c : x)) });
  }

  return (
    <View style={styles.free}>
      <Card>
        <Text style={styles.heading}>Writing task</Text>
        <Chips
          selected={taskId}
          onSelect={setTaskId}
          options={[
            { value: FREE, label: "Free writing" },
            ...(tasks.data ?? []).map((t) => ({
              value: t.id,
              label: t.done ? `${t.prompt} (done)` : t.prompt,
            })),
          ]}
        />
        {ideas.length > 0 && (
          <View style={styles.ideas}>
            <Text style={styles.muted}>Add a task:</Text>
            {ideas.map((i) => (
              <Button
                key={i.prompt}
                label={i.prompt}
                variant="secondary"
                busy={createTask.isPending}
                onPress={() =>
                  createTask.mutate(i, { onSuccess: (t) => setTaskId(t.id) })
                }
              />
            ))}
          </View>
        )}
        {createTask.isError && <ErrorText error={createTask.error} />}
      </Card>

      <Field
        label={task ? `${task.prompt} (at least ${task.min_sentences} sentences)` : "Write in German"}
        value={text}
        onChangeText={setText}
        multiline
        numberOfLines={5}
        maxLength={600}
        placeholder="Ich habe einen Tisch gekauft."
        style={styles.textArea}
        textAlignVertical="top"
      />
      <Text style={styles.muted}>
        {left ? `${left.remaining} ${left.label} left today` : ""}
      </Text>
      <Button
        label="Check my writing"
        onPress={submit}
        busy={check.isPending}
        disabled={!text.trim()}
      />
      {check.isError && <ErrorText error={check.error} />}

      {result && <CheckResultView result={result} onDecided={updated} />}

      {flagged.data && flagged.data.length > 0 && (
        <Card>
          <Text style={styles.heading}>Flagged for my teacher</Text>
          {flagged.data.map((c) => (
            <View key={c.id} style={styles.flagged}>
              <Text style={styles.body}>
                {c.sentence_wrong} → {c.sentence_correct}
              </Text>
            </View>
          ))}
        </Card>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  free: { gap: space.lg },
  intro: { fontSize: 15, lineHeight: 22, color: colors.muted, marginHorizontal: space.xs },
  linkTarget: { minHeight: TOUCH, justifyContent: "center", alignSelf: "flex-start" },
  link: { color: colors.primary, fontSize: 15, lineHeight: 22, fontWeight: "700" },
  lessonTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  lessonRow: { flexDirection: "row", alignItems: "center", gap: space.sm },
  lessonText: { flex: 1, gap: 2 },
  chapter: { fontSize: 13, lineHeight: 18, fontWeight: "800", color: colors.muted, letterSpacing: 0.4 },
  lessonTitle: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  heading: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  ideas: { gap: space.sm, marginTop: space.sm },
  textArea: { minHeight: 120 },
  flagged: { paddingVertical: space.xs },
}));
