import { router } from "expo-router";
import { RefreshControl, View } from "react-native";

import {
  KIND_LABELS,
  VERDICT_COLORS,
  countdown,
  useExams,
  type Exam,
} from "@/features/exams/api";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, Loading, Pill, SectionTitle } from "@/ui/components";
import { ChevronRight, ICON } from "@/ui/icons";
import { makeStyles, space, toneAccent, useTheme } from "@/ui/theme";

export default function Exams() {
  const styles = useStyles();
  const exams = useExams();

  if (exams.isPending) {
    return (
      <Centered>
        <Loading />
      </Centered>
    );
  }
  if (exams.isError) {
    return (
      <Centered>
        <ErrorText error={exams.error} />
        <Button label="Try again" variant="secondary" onPress={() => void exams.refetch()} />
      </Centered>
    );
  }

  const upcoming = exams.data.filter((e) => e.days_left >= 0);
  const past = exams.data.filter((e) => e.days_left < 0);

  return (
    <FormScroll
      contentContainerStyle={styles.page}
      refreshControl={
        <RefreshControl refreshing={exams.isRefetching} onRefresh={() => void exams.refetch()} />
      }
    >
      <Button label="Add a test" onPress={() => router.push("/exams/new")} />
      <Button
        label="Add a practice test result"
        variant="secondary"
        onPress={() => router.push("/exams/result")}
      />

      {upcoming.length === 0 && (
        <Card>
          <Text style={styles.body}>No tests coming up.</Text>
          <Text style={styles.muted}>
            Add your next internal test or the Goethe A1 exam to see a countdown, how ready you
            are, and what to revise.
          </Text>
        </Card>
      )}
      {upcoming.map((e, i) => (
        // The next test is the one glass card.
        <ExamCard key={e.id} exam={e} glass={i === 0} />
      ))}

      {past.length > 0 && <SectionTitle>Past tests</SectionTitle>}
      {past.map((e) => (
        <ExamCard key={e.id} exam={e} />
      ))}
    </FormScroll>
  );
}

function ExamCard({ exam, glass = false }: { exam: Exam; glass?: boolean }) {
  const colors = useTheme();
  const styles = useStyles();
  const verdict = exam.readiness?.verdict;
  return (
    <Card
      glass={glass}
      onPress={() => router.push({ pathname: "/exams/[id]", params: { id: exam.id } })}
      label={`${exam.title}, ${countdown(exam.days_left)}${exam.readiness ? `. ${exam.readiness.headline}` : ""}`}
    >
      <View style={styles.row}>
        <Text style={styles.title}>{exam.title}</Text>
        <ChevronRight size={ICON.bar} color={colors.muted} />
      </View>
      <Pill label={countdown(exam.days_left)} accent={toneAccent(colors, "primary")} />
      <Text style={styles.muted}>
        {KIND_LABELS[exam.kind]} · {exam.exam_date} ·{" "}
        {exam.whole_course ? "whole course" : `${exam.chapters.length} chapters`}
      </Text>
      {exam.readiness && verdict && (
        <Text style={[styles.verdict, { color: colors[VERDICT_COLORS[verdict]] }]}>
          {exam.readiness.headline}
        </Text>
      )}
      {exam.results_count > 0 && (
        <Text style={styles.muted}>
          {exam.results_count} result{exam.results_count === 1 ? "" : "s"} entered
        </Text>
      )}
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  title: { fontSize: 17, lineHeight: 24, fontWeight: "800", flex: 1 },
  body: { fontSize: 16, lineHeight: 24 },
  verdict: { fontSize: 15, lineHeight: 22, fontWeight: "700" },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  row: { flexDirection: "row", alignItems: "center", gap: space.md },
}));
