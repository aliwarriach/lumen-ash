import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, View } from "react-native";

import { PronounceButton } from "@/features/vocabulary/PronounceButton";
import { WordForm, type WordFormMode } from "@/features/vocabulary/WordForm";
import {
  KIND_LABELS,
  fromDictionary,
  useCreateWord,
  useLookup,
  type DictionaryEntry,
  type WordInput,
} from "@/features/vocabulary/api";
import { useDebounced } from "@/lib/useDebounced";
import { Button, Card, ErrorText, Field } from "@/ui/components";
import { ArrowRight, ICON } from "@/ui/icons";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

type Draft = {
  initial: Partial<WordInput>;
  meanings: string[];
  mode: WordFormMode;
  exampleTranslation: string | null;
};

/**
 * Step 1: look the word up. Step 2: a word found in the dictionary arrives with everything filled
 * in; one that isn't gets the short form.
 */
export default function NewWord() {
  const { chapterId } = useLocalSearchParams<{ chapterId?: string }>();
  const [draft, setDraft] = useState<Draft | null>(null);
  const create = useCreateWord();

  if (draft) {
    return (
      <WordForm
        initial={draft.initial}
        mode={draft.mode}
        suggestedMeanings={draft.meanings}
        exampleTranslation={draft.exampleTranslation}
        submitLabel="Save word"
        busy={create.isPending}
        error={create.error}
        onSubmit={(values) =>
          create.mutate(values, {
            onSuccess: (word) =>
              router.replace({ pathname: "/words/[id]", params: { id: word.id } }),
          })
        }
      />
    );
  }

  return (
    <LookupStep
      onPick={(entry) =>
        setDraft({
          initial: fromDictionary(entry, chapterId),
          meanings: entry.meanings,
          mode: "dictionary",
          exampleTranslation: entry.example_en ?? null,
        })
      }
      onManual={(german) =>
        setDraft({
          initial: { german, chapter_id: chapterId ?? null },
          meanings: [],
          mode: "manual",
          exampleTranslation: null,
        })
      }
    />
  );
}

function LookupStep({
  onPick,
  onManual,
}: {
  onPick: (entry: DictionaryEntry) => void;
  onManual: (german: string) => void;
}) {
  const styles = useStyles();
  const colors = useTheme();
  const [text, setText] = useState("");
  const q = useDebounced(text.trim());
  const lookup = useLookup(q);
  const result = q ? lookup.data : undefined;

  return (
    <FormScroll contentContainerStyle={styles.page}>
      <Field
        label="German word"
        value={text}
        onChangeText={setText}
        placeholder="e.g. Tisch, aufstehen"
        autoCapitalize="none"
        autoCorrect={false}
        autoFocus
      />
      {lookup.isFetching && <ActivityIndicator color={colors.primary} />}
      {lookup.isError && <ErrorText error={lookup.error} />}

      {result && result.saved.length > 0 && (
        <Card>
          <Text style={styles.warning}>Already in your words:</Text>
          {result.saved.map((s) => (
            <Text key={s.id} style={styles.body}>
              {s.german} ({KIND_LABELS[s.kind].toLowerCase()}): {s.meaning_en}
            </Text>
          ))}
        </Card>
      )}

      {result?.matched_form && result.entries.length > 0 && (
        <Text style={styles.muted}>“{result.matched_form}” is a form of:</Text>
      )}
      {result?.entries.map((entry) => (
        <EntryCard key={entry.key} entry={entry} onPress={() => onPick(entry)} />
      ))}

      {result && result.suggestions.length > 0 && (
        <View style={styles.suggestions}>
          {result.suggestions.map((s) => (
            <Pressable
              key={s}
              accessibilityRole="button"
              onPress={() => setText(s)}
              android_ripple={{ color: colors.divider }}
              style={styles.suggestion}
            >
              <Text style={styles.suggestionText}>{s}</Text>
            </Pressable>
          ))}
        </View>
      )}

      {result && result.entries.length === 0 && (
        <Text style={styles.muted}>
          Not found in the dictionary. You can still add it yourself: only the word and its meaning
          are needed.
        </Text>
      )}
      {q.length > 0 && (
        <Button label="Enter it myself" variant="secondary" onPress={() => onManual(result?.query ?? q)} />
      )}
      {result && <Text style={styles.attribution}>{result.attribution}</Text>}
    </FormScroll>
  );
}

function EntryCard({ entry, onPress }: { entry: DictionaryEntry; onPress: () => void }) {
  const styles = useStyles();
  const colors = useTheme();
  const isNoun = entry.kind === "noun";
  const head = isNoun && entry.articles.length ? `${entry.articles.join("/")} ${entry.lemma}` : entry.lemma;
  const detail = isNoun
    ? entry.plural_only
      ? "plural only"
      : entry.plurals.length
        ? `plural: die ${entry.plurals.join(", ")}`
        : "no plural"
    : entry.kind === "verb" && entry.verb_forms
      ? [entry.verb_forms.present?.er_sie_es, entry.verb_forms.past_participle]
          .filter(Boolean)
          .join(" · ")
      : KIND_LABELS[entry.kind];

  return (
    <Card onPress={onPress} label={`${head}, ${KIND_LABELS[entry.kind]}. ${entry.meanings.join(", ")}. Use this`}>
        <View style={styles.entryHeader}>
          <Text style={styles.headword}>{head}</Text>
          <Text style={styles.kind}>{KIND_LABELS[entry.kind]}</Text>
        </View>
        {detail ? <Text style={styles.muted}>{detail}</Text> : null}
        <Text style={styles.body} numberOfLines={2}>
          {entry.meanings.join(" · ")}
        </Text>
        <PronounceButton text={head} audioUrl={entry.audio_url} />
        {entry.example_de ? (
          <Text style={styles.muted} numberOfLines={2}>
            “{entry.example_de}”
          </Text>
        ) : null}
        <View style={styles.useRow}>
          <Text style={styles.use}>Use this</Text>
          <ArrowRight size={ICON.inline} color={colors.primary} />
        </View>
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  entryHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  headword: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  kind: { fontSize: 13, lineHeight: 18, fontWeight: "700", color: colors.muted },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  warning: { fontSize: 15, lineHeight: 22, color: colors.warning, fontWeight: "700" },
  useRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  use: { fontSize: 15, lineHeight: 22, color: colors.primary, fontWeight: "800" },
  suggestions: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  suggestion: {
    minHeight: TOUCH,
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primaryContainer,
    paddingHorizontal: space.lg,
    overflow: "hidden",
  },
  suggestionText: { fontSize: 15, lineHeight: 22, fontWeight: "700", color: colors.onPrimaryContainer },
  attribution: { fontSize: 13, lineHeight: 18, color: colors.muted, marginTop: space.md },
}));
