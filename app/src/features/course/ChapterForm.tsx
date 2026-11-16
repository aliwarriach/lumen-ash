import { useState } from "react";

import { parseTopics, type ChapterInput } from "@/features/course/api";
import { Button, ErrorText, Field } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { makeStyles, space } from "@/ui/theme";

type Props = {
  initial?: Partial<ChapterInput>;
  submitLabel: string;
  onSubmit: (values: ChapterInput) => void;
  busy: boolean;
  error: unknown;
};

export function ChapterForm({ initial, submitLabel, onSubmit, busy, error }: Props) {
  const styles = useStyles();
  const [number, setNumber] = useState(initial?.number ? String(initial.number) : "");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [topics, setTopics] = useState((initial?.topics ?? []).join("\n"));
  const [notes, setNotes] = useState(initial?.notes ?? "");

  const parsedNumber = Number.parseInt(number, 10);
  const valid = parsedNumber >= 1 && parsedNumber <= 99 && title.trim().length > 0;

  return (
    <FormScroll contentContainerStyle={styles.form}>
      <Field
        label="Chapter number"
        keyboardType="number-pad"
        value={number}
        onChangeText={setNumber}
        placeholder="1"
      />
      <Field label="Title" value={title} onChangeText={setTitle} placeholder="As in your book" />
      <Field
        label="Main topics (one per line)"
        value={topics}
        onChangeText={setTopics}
        multiline
        style={styles.tall}
      />
      <Field label="Notes" value={notes} onChangeText={setNotes} multiline style={styles.tall} />
      {error != null && <ErrorText error={error} />}
      <Button
        label={submitLabel}
        busy={busy}
        disabled={!valid}
        onPress={() =>
          onSubmit({
            number: parsedNumber,
            title: title.trim(),
            topics: parseTopics(topics),
            notes: notes.trim() || null,
          })
        }
      />
    </FormScroll>
  );
}

const useStyles = makeStyles(() => ({
  form: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  tall: { minHeight: 90, textAlignVertical: "top" },
}));
