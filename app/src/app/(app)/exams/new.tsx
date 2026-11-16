import { router } from "expo-router";
import { useState } from "react";

import { useChapters } from "@/features/course/api";
import {
  KIND_LABELS,
  isValidIsoDate,
  isoDate,
  useCreateExam,
  type ExamKind,
} from "@/features/exams/api";
import { Button, Chips, ErrorText, Field, MultiChips } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { makeStyles, space } from "@/ui/theme";

const KINDS = (Object.keys(KIND_LABELS) as ExamKind[]).map((k) => ({
  value: k,
  label: KIND_LABELS[k],
}));

export default function NewExam() {
  const styles = useStyles();
  const create = useCreateExam();
  const chapters = useChapters();
  const [kind, setKind] = useState<ExamKind>("internal");
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(isoDate(14));
  const [target, setTarget] = useState("85");
  const [chapterIds, setChapterIds] = useState<string[]>([]);

  const goal = Number.parseInt(target, 10);
  const valid =
    title.trim().length > 0 && isValidIsoDate(date) && goal >= 1 && goal <= 100;

  function toggle(id: string) {
    setChapterIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  }

  return (
    <FormScroll contentContainerStyle={styles.form}>
      <Chips label="Which test?" options={KINDS} selected={kind} onSelect={setKind} />
      <Field
        label="Name"
        value={title}
        onChangeText={setTitle}
        placeholder={kind === "goethe_a1" ? "Goethe A1" : "Internal test 1"}
      />
      <Field
        label="Date (year-month-day)"
        value={date}
        onChangeText={setDate}
        placeholder="2026-12-15"
        autoCapitalize="none"
        keyboardType="numbers-and-punctuation"
      />
      {date.length > 0 && !isValidIsoDate(date) && (
        <Text style={styles.warning}>Write the date like 2026-12-15.</Text>
      )}
      <Field
        label="Your goal (% you want to reach)"
        value={target}
        onChangeText={setTarget}
        keyboardType="number-pad"
      />
      <MultiChips
        label="Chapters it covers (none selected means the whole course)"
        options={(chapters.data ?? []).map((c) => ({
          value: c.id,
          label: `${c.number}. ${c.title}`,
        }))}
        selected={chapterIds}
        onToggle={toggle}
      />
      {create.isError && <ErrorText error={create.error} />}
      <Button
        label="Add test"
        busy={create.isPending}
        disabled={!valid}
        onPress={() =>
          create.mutate(
            {
              kind,
              title: title.trim(),
              exam_date: date,
              target_percent: goal,
              chapter_ids: chapterIds,
            },
            {
              onSuccess: (exam) =>
                router.replace({ pathname: "/exams/[id]", params: { id: exam.id } }),
            },
          )
        }
      />
    </FormScroll>
  );
}

const useStyles = makeStyles((colors) => ({
  form: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  warning: { fontSize: 14, lineHeight: 20, color: colors.warning },
}));
