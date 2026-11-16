import { Stack, router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, View } from "react-native";

import { PronounceButton } from "@/features/vocabulary/PronounceButton";
import {
  KIND_LABELS,
  PERSONS,
  STAGE_LABELS,
  headword,
  useDeleteWord,
  useWord,
  useWordReviews,
} from "@/features/vocabulary/api";
import { useChapters } from "@/features/course/api";
import { MistakeRow } from "@/features/mistakes/MistakeRow";
import { useMistakes } from "@/features/mistakes/api";
import { STAGE_EXPLANATIONS } from "@/features/review/api";
import { AskCommunityButton } from "@/features/community/AskCommunity";
import { aboutWord } from "@/features/community/ask";
import { Check, ICON, X } from "@/ui/icons";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, IconLabel, Pill, SectionTitle } from "@/ui/components";
import { makeStyles, space, useTheme, type Accent } from "@/ui/theme";

const CARD_LABELS = {
  recall: "Recalled the meaning",
  produce: "Typed the German",
  article: "Article and plural",
  sentence: "Own sentence",
  error_retry: "Mistake retry",
} as const;

export default function WordDetail() {
  const colors = useTheme();
  const styles = useStyles();
  const { id } = useLocalSearchParams<{ id: string }>();
  const word = useWord(id);
  const chapters = useChapters();
  const remove = useDeleteWord(id);
  const history = useWordReviews(id);
  const mistakes = useMistakes({ wordId: id });

  if (word.isPending) {
    return (
      <Centered>
        <ActivityIndicator color={colors.primary} />
      </Centered>
    );
  }
  if (word.isError) {
    return (
      <Centered>
        <ErrorText error={word.error} />
      </Centered>
    );
  }

  const w = word.data;
  const chapter = chapters.data?.find((c) => c.id === w.chapter_id);
  const vf = w.verb_forms;
  // The stage, by plain rule: a green pill once the word is known, a tint while it is being learned.
  const stageAccent: Accent =
    w.stage === "mastered"
      ? colors.green
      : w.stage === "new"
        ? { fg: colors.muted, bg: colors.well }
        : { fg: colors.onPrimaryContainer, bg: colors.primaryContainer };

  function confirmDelete() {
    Alert.alert(`Delete "${headword(w)}"?`, undefined, [
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
      <Stack.Screen options={{ title: w.german }} />
      <FormScroll contentContainerStyle={styles.page}>
        <Card glass>
          <View style={styles.pills}>
            <Pill label={KIND_LABELS[w.kind]} accent={{ fg: colors.muted, bg: colors.well }} />
            <Pill label={STAGE_LABELS[w.stage]} accent={stageAccent} icon={w.stage === "mastered" ? Check : undefined} />
          </View>
          <Text style={styles.headword} accessibilityRole="header" accessibilityLabel={headword(w)}>
            {w.article && <Text style={{ color: colors[w.article].text }}>{w.article} </Text>}
            {w.german}
          </Text>
          <Text style={styles.muted}>{STAGE_EXPLANATIONS[w.stage]}</Text>
          {w.kind === "noun" && (
            <Text style={styles.muted}>
              {w.plural_only ? "Plural only" : w.plural ? `Plural: die ${w.plural}` : "No plural"}
            </Text>
          )}
          {w.ipa && <Text style={styles.muted}>{w.ipa}</Text>}
          <PronounceButton text={headword(w)} audioUrl={w.audio_url} />
          <Text style={styles.meaning}>{w.meaning_en}</Text>
          {w.meaning_ur && <Text style={styles.meaning}>{w.meaning_ur}</Text>}
        </Card>

        <AskCommunityButton attachment={() => aboutWord(w)} />

        {vf && (
          <Card>
            <SectionTitle>Present tense</SectionTitle>
            {PERSONS.map((p) =>
              vf.present?.[p.key] ? (
                <View key={p.key} style={styles.conjRow}>
                  <Text style={styles.person}>{p.label}</Text>
                  <Text style={styles.body}>{vf.present[p.key]}</Text>
                </View>
              ) : null,
            )}
            {vf.past_participle && (
              <Text style={styles.body}>
                Perfekt: {vf.auxiliary ?? "haben/sein"} … {vf.past_participle}
              </Text>
            )}
            {vf.separable && <Text style={styles.muted}>Separable verb</Text>}
            {w.sentence_pattern && <Text style={styles.body}>Pattern: {w.sentence_pattern}</Text>}
          </Card>
        )}

        {(w.example_sentence || w.personal_sentence) && (
          <Card>
            {w.example_sentence && (
              <>
                <SectionTitle>Example</SectionTitle>
                <Text style={styles.body}>{w.example_sentence}</Text>
              </>
            )}
            {w.personal_sentence && (
              <>
                <SectionTitle>My sentence</SectionTitle>
                <Text style={styles.body}>{w.personal_sentence}</Text>
              </>
            )}
          </Card>
        )}

        {history.data && history.data.length > 0 && (
          <Card>
            <SectionTitle>Recent answers</SectionTitle>
            {history.data.slice(0, 8).map((h) => (
              <IconLabel
                key={h.reviewed_at + h.card_type}
                icon={h.correct ? Check : X}
                size={ICON.small}
                color={h.correct ? colors.success : colors.danger}
                style={styles.body}
              >
                {h.answer ?? CARD_LABELS[h.card_type]}
                {!h.correct && h.expected ? `  →  ${h.expected}` : ""}
                {!h.checked ? " (self-rated)" : ""}
              </IconLabel>
            ))}
          </Card>
        )}

        {mistakes.data && mistakes.data.length > 0 && (
          <>
            <SectionTitle>My mistakes with this word</SectionTitle>
            {mistakes.data.slice(0, 5).map((m) => (
              <MistakeRow key={m.id} mistake={m} />
            ))}
          </>
        )}
        <Button
          label="Log a mistake with this word"
          variant="secondary"
          onPress={() => router.push({ pathname: "/mistakes/new", params: { wordId: w.id } })}
        />

        <Text style={styles.muted}>
          {[chapter && `Kapitel ${chapter.number}`, w.source].filter(Boolean).join(" · ")}
        </Text>
        {w.dictionary_key && (
          <Text style={styles.attribution}>
            Word data from Wiktionary (CC BY-SA 4.0), via kaikki.org. Recordings from Wikimedia
            Commons.
          </Text>
        )}

        <Button
          label="Edit"
          variant="secondary"
          onPress={() => router.push({ pathname: "/words/[id]/edit", params: { id: w.id } })}
        />
        <Button label="Delete" variant="danger" busy={remove.isPending} onPress={confirmDelete} />
      </FormScroll>
    </>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  pills: { flexDirection: "row", gap: space.sm },
  headword: { fontSize: 34, lineHeight: 42, fontWeight: "800" },
  meaning: { fontSize: 18, lineHeight: 26, fontWeight: "600" },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  conjRow: { flexDirection: "row", gap: space.md },
  person: { width: 72, fontSize: 16, lineHeight: 24, color: colors.muted },
  attribution: { fontSize: 13, lineHeight: 18, color: colors.muted },
}));
