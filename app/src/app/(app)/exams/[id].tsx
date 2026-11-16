import { router, Stack, useLocalSearchParams } from "expo-router";
import { Alert, View } from "react-native";

import {
  KIND_LABELS,
  SKILL_LABELS,
  VERDICT_COLORS,
  VERDICT_LABELS,
  countdown,
  useDeleteExam,
  useDeleteResult,
  useExam,
  type ChapterReadiness,
  type ExamDetail,
  type ExamResult,
  type Skill,
  type SkillReadiness,
} from "@/features/exams/api";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, Loading, Pill, ProgressBar, SectionTitle, TextLink } from "@/ui/components";
import { makeStyles, space, toneAccent, useTheme } from "@/ui/theme";

const pct = (n: number | null | undefined) => (n == null ? "no evidence yet" : `${Math.round(n)}%`);

export default function ExamScreen() {
  const styles = useStyles();
  const colors = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const exam = useExam(id);
  const remove = useDeleteExam(id);

  if (exam.isPending) {
    return (
      <Centered>
        <Loading />
      </Centered>
    );
  }
  if (exam.isError) {
    return (
      <Centered>
        <ErrorText error={exam.error} />
        <Button label="Try again" variant="secondary" onPress={() => void exam.refetch()} />
      </Centered>
    );
  }

  const e = exam.data;
  function confirmDelete() {
    Alert.alert(`Delete ${e.title}?`, "Results you entered for it are kept.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => remove.mutate(undefined, { onSuccess: () => router.back() }),
      },
    ]);
  }

  return (
    <>
      <Stack.Screen options={{ title: e.title }} />
      <FormScroll contentContainerStyle={styles.page}>
        <Card glass>
          <Pill label={countdown(e.days_left)} accent={toneAccent(colors, "primary")} />
          <Text style={styles.title} accessibilityRole="header">
            {e.title}
          </Text>
          <Text style={styles.muted}>
            {KIND_LABELS[e.kind]} · {e.exam_date} · your goal {e.target_percent}% ·{" "}
            {e.whole_course
              ? "covers the whole course"
              : `covers ${e.chapters.map((c) => c.number).join(", ")}`}
          </Text>
        </Card>

        {e.readiness_detail ? <ReadinessCard exam={e} /> : <PastCard exam={e} />}
        {e.revision && e.revision.schedule.length > 0 && <Revision exam={e} />}
        {e.readiness_detail && <Chapters chapters={e.readiness_detail.chapters} />}
        {e.readiness_detail && <Skills skills={e.readiness_detail.skills} />}
        <Results results={e.results} examId={e.id} />

        <Button label="Delete this test" variant="danger" onPress={confirmDelete} />
      </FormScroll>
    </>
  );
}

function ReadinessCard({ exam }: { exam: ExamDetail }) {
  const colors = useTheme();
  const styles = useStyles();
  const r = exam.readiness_detail!;
  return (
    <View style={styles.section}>
      <SectionTitle>Am I ready?</SectionTitle>
      <Card>
        <Pill label={VERDICT_LABELS[r.verdict]} accent={toneAccent(colors, VERDICT_COLORS[r.verdict])} />
        <Text style={styles.big}>{r.headline}</Text>
        {r.scope_note && <Text style={styles.body}>{r.scope_note}</Text>}
        {r.estimate != null && (
          <>
            <ProgressBar value={r.estimate / 100} color={colors.illustration.teal} label={`Readiness ${Math.round(r.estimate)}%`} />
            <Text style={styles.muted}>
              Rough estimate {Math.round(r.estimate)}% against your goal of {r.target}%. It is not a
              prediction of your mark.
            </Text>
          </>
        )}
        <Text style={styles.muted}>
          From what the app has seen you learn: {pct(r.learning_score)}. Recent practice tests:{" "}
          {r.practice_score == null ? "none entered" : pct(r.practice_score)}. Chapters with
          evidence: {r.chapters_with_evidence} of {r.chapters_total}.
        </Text>
        {r.reasons.map((reason) => (
          <Text key={reason} style={styles.body}>
            • {reason}
          </Text>
        ))}
      </Card>
    </View>
  );
}

function PastCard({ exam }: { exam: ExamDetail }) {
  const styles = useStyles();
  return (
    <Card>
      <Text style={styles.body}>This test has passed.</Text>
      {exam.results.length === 0 && (
        <Text style={styles.muted}>Record your result below so the app can update your weak areas.</Text>
      )}
    </Card>
  );
}

function Revision({ exam }: { exam: ExamDetail }) {
  const styles = useStyles();
  const days = exam.revision!.schedule;
  const [today, ...rest] = days;
  return (
    <View style={styles.section}>
      <SectionTitle>Revision plan</SectionTitle>
      <Card>
        <Text style={styles.body}>
          Today: Chapter {today.chapter.number}, {today.minutes} minutes
        </Text>
        <Text style={styles.muted}>{today.why}</Text>
        {today.words.length > 0 && (
          <Text style={styles.body}>Words to revise: {today.words.join(", ")}</Text>
        )}
        {rest.length > 0 && <Text style={styles.sub}>Coming days</Text>}
        {rest.slice(0, 6).map((d) => (
          <Text key={d.day} style={styles.muted}>
            {d.day} · {countdown(d.days_left)} · Chapter {d.chapter.number} · {d.minutes} min
          </Text>
        ))}
      </Card>
    </View>
  );
}

function Chapters({ chapters }: { chapters: ChapterReadiness[] }) {
  const styles = useStyles();
  const colors = useTheme();
  if (chapters.length === 0) return null;
  return (
    <View style={styles.section}>
      <SectionTitle>By chapter</SectionTitle>
      {chapters.map((c) => (
        <Card key={c.id}>
          <View style={styles.row}>
            <Text style={styles.body}>
              {c.number}. {c.title}
            </Text>
            <Text style={[styles.score, { color: c.needs_work ? colors.danger : colors.success }]}>
              {c.score == null ? "–" : `${Math.round(c.score)}%`}
            </Text>
          </View>
          <Text style={styles.muted}>{c.detail}</Text>
          {c.weak_patterns.length > 0 && (
            <Text style={styles.muted}>Grammar to work on: {c.weak_patterns.join(", ")}</Text>
          )}
          {c.lost_marks_in.length > 0 && (
            <Text style={styles.muted}>You lost marks here in: {c.lost_marks_in.join(", ")}</Text>
          )}
          {c.needs_work && c.unsecure_words.length > 0 && (
            <Text style={styles.muted}>Words not secure yet: {c.unsecure_words.join(", ")}</Text>
          )}
        </Card>
      ))}
    </View>
  );
}

function Skills({ skills }: { skills: SkillReadiness[] }) {
  const styles = useStyles();
  return (
    <View style={styles.section}>
      <SectionTitle>By skill</SectionTitle>
      <Card>
        {skills.map((s) => (
          <View key={s.skill} style={styles.skill}>
            <View style={styles.row}>
              <Text style={styles.body}>{SKILL_LABELS[s.skill as Skill] ?? s.skill}</Text>
              <Text style={styles.body}>{s.score == null ? "–" : `${Math.round(s.score)}%`}</Text>
            </View>
            <Text style={styles.muted}>{s.detail}</Text>
          </View>
        ))}
      </Card>
    </View>
  );
}

function Results({ results, examId }: { results: ExamResult[]; examId: string }) {
  const styles = useStyles();
  const remove = useDeleteResult();
  function confirmDelete(r: ExamResult) {
    Alert.alert("Delete this result?", undefined, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => remove.mutate(r.id) },
    ]);
  }
  return (
    <View style={styles.section}>
      <SectionTitle>Results</SectionTitle>
      {results.map((r) => (
        <Card key={r.id}>
          <View style={styles.row}>
            <Text style={styles.body}>{r.title ?? (r.kind === "exam" ? "The real test" : "Practice test")}</Text>
            <Text style={styles.score}>{Math.round(r.percent)}%</Text>
          </View>
          <Text style={styles.muted}>
            {r.taken_on} · {r.score} of {r.max_score}
            {r.kind === "exam" ? " · real result" : ""}
          </Text>
          {r.sections.map((s) => (
            <Text key={s.skill} style={styles.muted}>
              {SKILL_LABELS[s.skill]}: {s.score} of {s.max_score}
            </Text>
          ))}
          {r.weak_chapters.length > 0 && (
            <Text style={styles.muted}>
              Lost marks in chapters {r.weak_chapters.map((c) => c.number).join(", ")}
            </Text>
          )}
          <TextLink label="Delete result" tone="danger" onPress={() => confirmDelete(r)} />
        </Card>
      ))}
      <Button
        label="Add a result"
        variant="secondary"
        onPress={() => router.push({ pathname: "/exams/result", params: { exam_id: examId } })}
      />
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.xl },
  section: { gap: space.md - 2 },
  sub: { fontSize: 15, lineHeight: 22, fontWeight: "800", marginTop: space.sm },
  title: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  big: { fontSize: 17, lineHeight: 24, fontWeight: "700" },
  body: { fontSize: 15, lineHeight: 22, flexShrink: 1 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  score: { fontSize: 16, lineHeight: 22, fontWeight: "800" },
  row: { flexDirection: "row", justifyContent: "space-between", gap: space.md },
  skill: { gap: 2, marginBottom: space.sm },
}));
