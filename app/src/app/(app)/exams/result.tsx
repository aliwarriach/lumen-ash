import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { View } from "react-native";

import { useChapters } from "@/features/course/api";
import {
  isValidIsoDate,
  isoDate,
  useCreateResult,
  type ResultKind,
  type Skill,
} from "@/features/exams/api";
import { Button, Chips, ErrorText, Field, MultiChips } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { makeStyles, space } from "@/ui/theme";

const KINDS: { value: ResultKind; label: string }[] = [
  { value: "practice", label: "Practice test" },
  { value: "exam", label: "The real test" },
];

// Goethe A1 has four parts; each is usually worth 25 points.
const SECTIONS: { skill: Skill; label: string }[] = [
  { skill: "reading", label: "Reading" },
  { skill: "listening", label: "Listening" },
  { skill: "writing", label: "Writing" },
  { skill: "speaking", label: "Speaking" },
];

export default function NewResult() {
  const styles = useStyles();
  const { exam_id } = useLocalSearchParams<{ exam_id?: string }>();
  const create = useCreateResult();
  const chapters = useChapters();
  const [kind, setKind] = useState<ResultKind>(exam_id ? "exam" : "practice");
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(isoDate());
  const [score, setScore] = useState("");
  const [max, setMax] = useState("100");
  const [parts, setParts] = useState<Record<string, { score: string; max: string }>>({});
  const [weak, setWeak] = useState<string[]>([]);

  const total = Number(score);
  const outOf = Number(max);
  const valid =
    score.trim() !== "" &&
    Number.isFinite(total) &&
    outOf > 0 &&
    total >= 0 &&
    total <= outOf &&
    isValidIsoDate(date);

  const sections = SECTIONS.flatMap(({ skill }) => {
    const p = parts[skill];
    if (!p || p.score.trim() === "") return [];
    return [{ skill, score: Number(p.score), max_score: Number(p.max || "25") }];
  });
  const sectionsOk = sections.every((s) => s.score >= 0 && s.max_score > 0 && s.score <= s.max_score);

  function setPart(skill: string, field: "score" | "max", value: string) {
    setParts((p) => {
      const current = p[skill] ?? { score: "", max: "25" };
      return { ...p, [skill]: { ...current, [field]: value } };
    });
  }

  return (
    <FormScroll contentContainerStyle={styles.form}>
      <Chips label="What is it?" options={KINDS} selected={kind} onSelect={setKind} />
      <Field
        label="Name (optional)"
        value={title}
        onChangeText={setTitle}
        placeholder="Goethe Modelltest 2"
      />
      <Field
        label="Date taken (year-month-day)"
        value={date}
        onChangeText={setDate}
        autoCapitalize="none"
        keyboardType="numbers-and-punctuation"
      />
      <View style={styles.pair}>
        <View style={styles.half}>
          <Field label="Your score" value={score} onChangeText={setScore} keyboardType="decimal-pad" />
        </View>
        <View style={styles.half}>
          <Field label="Out of" value={max} onChangeText={setMax} keyboardType="decimal-pad" />
        </View>
      </View>

      <Text style={styles.heading}>Scores for each part (optional)</Text>
      <Text style={styles.muted}>
        The app cannot see your reading, listening, writing or speaking, so these only count if you
        enter them.
      </Text>
      {SECTIONS.map(({ skill, label }) => (
        <View key={skill} style={styles.pair}>
          <View style={styles.half}>
            <Field
              label={label}
              value={parts[skill]?.score ?? ""}
              onChangeText={(v) => setPart(skill, "score", v)}
              keyboardType="decimal-pad"
              placeholder="score"
            />
          </View>
          <View style={styles.half}>
            <Field
              label="Out of"
              value={parts[skill]?.max ?? "25"}
              onChangeText={(v) => setPart(skill, "max", v)}
              keyboardType="decimal-pad"
            />
          </View>
        </View>
      ))}

      <MultiChips
        label="Chapters where you lost marks (optional)"
        options={(chapters.data ?? []).map((c) => ({
          value: c.id,
          label: `${c.number}. ${c.title}`,
        }))}
        selected={weak}
        onToggle={(id) => setWeak((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]))}
      />

      {create.isError && <ErrorText error={create.error} />}
      <Button
        label="Save result"
        busy={create.isPending}
        disabled={!valid || !sectionsOk}
        onPress={() =>
          create.mutate(
            {
              exam_id: exam_id ?? null,
              kind,
              title: title.trim() || null,
              taken_on: date,
              score: total,
              max_score: outOf,
              sections,
              weak_chapter_ids: weak,
            },
            { onSuccess: () => router.back() },
          )
        }
      />
    </FormScroll>
  );
}

const useStyles = makeStyles((colors) => ({
  form: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  heading: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  pair: { flexDirection: "row", gap: space.md },
  half: { flex: 1 },
}));
