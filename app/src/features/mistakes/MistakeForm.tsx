import { useState } from "react";
import { Pressable, View } from "react-native";

import { useChapters } from "@/features/course/api";
import {
  CATEGORY_LABELS,
  usePatterns,
  type MistakeCategory,
  type PatternKey,
} from "@/features/grammar/api";
import type { MistakeInput } from "@/features/mistakes/api";
import { headword, useWords } from "@/features/vocabulary/api";
import { useDebounced } from "@/lib/useDebounced";
import { Button, Chips, ErrorText, Field, MultiChips } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

type LinkedWord = { id: string; german: string; article: "der" | "die" | "das" | null };

export type MistakeFormInitial = Partial<Omit<MistakeInput, "word_ids">> & { words?: LinkedWord[] };

type Props = {
  initial?: MistakeFormInitial;
  submitLabel: string;
  onSubmit: (values: MistakeInput) => void;
  busy: boolean;
  error: unknown;
};

const CATEGORIES = (Object.keys(CATEGORY_LABELS) as MistakeCategory[]).map((c) => ({
  value: c,
  label: CATEGORY_LABELS[c],
}));
const orNull = (s: string) => s.trim() || null;

export function MistakeForm({ initial = {}, submitLabel, onSubmit, busy, error }: Props) {
  const styles = useStyles();
  const colors = useTheme();
  const chapters = useChapters();
  const patterns = usePatterns();
  const [wrong, setWrong] = useState(initial.wrong ?? "");
  const [correct, setCorrect] = useState(initial.correct ?? "");
  const [patternKey, setPatternKey] = useState<PatternKey | null>(initial.pattern_key ?? null);
  const [category, setCategory] = useState<MistakeCategory | null>(initial.category ?? null);
  const [explanation, setExplanation] = useState(initial.explanation ?? "");
  const [chapterId, setChapterId] = useState<string | null>(initial.chapter_id ?? null);
  const [source, setSource] = useState(initial.source ?? "");
  const [words, setWords] = useState<LinkedWord[]>(initial.words ?? []);
  const [wordSearch, setWordSearch] = useState("");
  const q = useDebounced(wordSearch.trim());
  const found = useWords({ q });

  const patternList = patterns.data ?? [];
  // Picking a pattern fills in its category; the learner can still change it.
  function pickPattern(key: PatternKey | "") {
    const next = key || null;
    setPatternKey(next);
    const p = patternList.find((x) => x.key === next);
    if (p) setCategory(p.category);
  }

  const same = wrong.trim() !== "" && wrong.trim() === correct.trim();
  const valid = wrong.trim() && correct.trim() && !same && (category || patternKey);
  const suggestions =
    q && found.data ? found.data.filter((w) => !words.some((x) => x.id === w.id)).slice(0, 5) : [];

  function submit() {
    onSubmit({
      wrong: wrong.trim(),
      correct: correct.trim(),
      pattern_key: patternKey,
      category,
      explanation: orNull(explanation),
      chapter_id: chapterId,
      source: orNull(source),
      word_ids: words.map((w) => w.id),
    });
  }

  return (
    <FormScroll contentContainerStyle={styles.form}>
      <Field
        label="What I wrote or said"
        value={wrong}
        onChangeText={setWrong}
        multiline
        autoCorrect={false}
        placeholder="Ich habe ein Tisch gekauft."
      />
      <Field
        label="The correct version"
        value={correct}
        onChangeText={setCorrect}
        multiline
        autoCorrect={false}
        placeholder="Ich habe einen Tisch gekauft."
      />
      {same && <Text style={styles.warning}>The two versions are the same.</Text>}

      <Chips
        label="Grammar rule"
        options={[
          { value: "", label: "Not sure" },
          ...patternList.map((p) => ({ value: p.key, label: p.title })),
        ]}
        selected={patternKey ?? ""}
        onSelect={pickPattern}
      />
      <Chips label="Kind of mistake" options={CATEGORIES} selected={category} onSelect={setCategory} />
      <Field
        label="Why (optional)"
        value={explanation}
        onChangeText={setExplanation}
        multiline
        placeholder="e.g. Tisch is masculine, and it's the object: einen."
      />

      <View style={styles.group}>
        <Text style={styles.label}>Words involved</Text>
        {words.length > 0 && (
          <MultiChips
            options={words.map((w) => ({ value: w.id, label: `${headword(w)}  ×` }))}
            selected={words.map((w) => w.id)}
            onToggle={(id) => setWords((ws) => ws.filter((w) => w.id !== id))}
          />
        )}
        <Field
          label=""
          accessibilityLabel="Search your words"
          value={wordSearch}
          onChangeText={setWordSearch}
          placeholder="Search your words"
          autoCapitalize="none"
        />
        {suggestions.map((w) => (
          <Pressable
            key={w.id}
            accessibilityRole="button"
            accessibilityLabel={`Add ${headword(w)}, ${w.meaning_en}`}
            onPress={() => {
              setWords((ws) => [...ws, { id: w.id, german: w.german, article: w.article }]);
              setWordSearch("");
            }}
            android_ripple={{ color: colors.divider }}
            style={styles.suggestion}
          >
            <Text style={styles.suggestionText}>
              + {headword(w)} <Text style={styles.muted}>{w.meaning_en}</Text>
            </Text>
          </Pressable>
        ))}
      </View>

      {chapters.data && chapters.data.length > 0 && (
        <Chips
          label="Chapter"
          options={[
            { value: "", label: "None" },
            ...chapters.data.map((c) => ({ value: c.id, label: `Kapitel ${c.number}` })),
          ]}
          selected={chapterId ?? ""}
          onSelect={(v) => setChapterId(v || null)}
        />
      )}
      <Field
        label="Where (optional)"
        value={source}
        onChangeText={setSource}
        placeholder="e.g. Homework S. 31, class test"
      />

      {error != null && <ErrorText error={error} />}
      <Button label={submitLabel} busy={busy} disabled={!valid} onPress={submit} />
    </FormScroll>
  );
}

const useStyles = makeStyles((colors) => ({
  form: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  group: { gap: space.sm },
  label: { fontSize: 14, lineHeight: 20, fontWeight: "600", color: colors.muted },
  warning: { fontSize: 14, lineHeight: 20, color: colors.warning },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted, fontWeight: "400" },
  suggestion: {
    minHeight: TOUCH,
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primaryContainer,
    paddingHorizontal: space.lg,
    overflow: "hidden",
  },
  suggestionText: { color: colors.onPrimaryContainer, fontSize: 15, lineHeight: 22, fontWeight: "700" },
}));
