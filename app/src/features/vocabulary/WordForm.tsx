import { useState } from "react";
import { Pressable, Switch, View } from "react-native";

import { useChapters } from "@/features/course/api";
import {
  KIND_LABELS,
  PERSONS,
  type Article,
  type VerbForms,
  type WordInput,
  type WordKind,
} from "@/features/vocabulary/api";
import { guessKind, summarize } from "@/features/vocabulary/guess";
import { PronounceButton } from "@/features/vocabulary/PronounceButton";
import { Button, Card, Chips, ErrorText, Field, IconLabel, TextLink } from "@/ui/components";
import { ArticleButtons } from "@/features/vocabulary/ArticleButtons";
import { FormScroll } from "@/ui/FormScroll";
import { ChevronDown, ChevronUp } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

/**
 * How much of the form to show.
 *  dictionary  the word was found: its details are already filled in and only summarised
 *  manual      not in the dictionary: just the word, its type and the meaning
 *  edit        a saved word being changed: everything
 * In the first two, the rest sits under "More details (optional)".
 */
export type WordFormMode = "dictionary" | "manual" | "edit";

type Props = {
  initial?: Partial<WordInput>;
  mode?: WordFormMode;
  /** Meanings offered by the dictionary; tapping one fills the English meaning. */
  suggestedMeanings?: string[];
  /** The English translation of the example sentence, shown under it. Not stored. */
  exampleTranslation?: string | null;
  submitLabel: string;
  onSubmit: (values: WordInput) => void;
  busy: boolean;
  error: unknown;
};

const KINDS = (Object.keys(KIND_LABELS) as WordKind[]).map((k) => ({
  value: k,
  label: KIND_LABELS[k],
}));
const AUXILIARIES = [
  { value: "haben", label: "haben" },
  { value: "sein", label: "sein" },
  { value: "haben/sein", label: "both" },
];

const emptyVerbForms: VerbForms = { present: {}, separable: false };
const orNull = (s: string) => s.trim() || null;

export function WordForm({
  initial = {},
  mode = "edit",
  suggestedMeanings = [],
  exampleTranslation = null,
  submitLabel,
  onSubmit,
  busy,
  error,
}: Props) {
  const colors = useTheme();
  const styles = useStyles();
  const chapters = useChapters();
  const [kind, setKind] = useState<WordKind>(initial.kind ?? guessKind(initial.german ?? ""));
  const [kindTouched, setKindTouched] = useState(initial.kind != null);
  const [german, setGerman] = useState(initial.german ?? "");
  const [article, setArticle] = useState<Article | null>(initial.article ?? null);
  const [plural, setPlural] = useState(initial.plural ?? "");
  const [pluralOnly, setPluralOnly] = useState(initial.plural_only ?? false);
  const [meaningEn, setMeaningEn] = useState(initial.meaning_en ?? "");
  const [meaningUr, setMeaningUr] = useState(initial.meaning_ur ?? "");
  const [example, setExample] = useState(initial.example_sentence ?? "");
  const [personal, setPersonal] = useState(initial.personal_sentence ?? "");
  const [pattern, setPattern] = useState(initial.sentence_pattern ?? "");
  const [verb, setVerb] = useState<VerbForms>(initial.verb_forms ?? emptyVerbForms);
  const [chapterId, setChapterId] = useState<string | null>(initial.chapter_id ?? null);
  const [source, setSource] = useState(initial.source ?? "");

  // What is folded away: "More details" in the short modes, and the dictionary's own details
  // (article, plural, verb forms) until the learner asks to change them.
  const [showMore, setShowMore] = useState(mode === "edit");
  const [editDetails, setEditDetails] = useState(mode !== "dictionary");

  const isNoun = kind === "noun";
  const isVerb = kind === "verb";
  const valid = german.trim().length > 0 && meaningEn.trim().length > 0;
  const spoken = isNoun && article && !pluralOnly ? `${article} ${german.trim()}` : german.trim();
  // The dictionary's recording, if the word came from it; otherwise the phone's voice.
  const pronounce = spoken ? <PronounceButton text={spoken} audioUrl={initial.audio_url} /> : null;
  const otherMeanings = suggestedMeanings.filter((m) => m !== meaningEn);

  function setPresent(key: keyof VerbForms["present"], value: string) {
    setVerb((v) => ({ ...v, present: { ...v.present, [key]: value || null } }));
  }

  function changeGerman(text: string) {
    setGerman(text);
    // Until the learner picks a type themselves, keep the guess in step with what they type.
    if (!kindTouched && mode === "manual") setKind(guessKind(text));
  }

  function submit() {
    onSubmit({
      dictionary_key: initial.dictionary_key ?? null,
      ipa: initial.ipa ?? null,
      audio_url: initial.audio_url ?? null,
      kind,
      german: german.trim(),
      article: isNoun ? (pluralOnly ? "die" : article) : null,
      plural: isNoun && !pluralOnly ? orNull(plural) : null,
      plural_only: isNoun && pluralOnly,
      meaning_en: meaningEn.trim(),
      meaning_ur: orNull(meaningUr),
      example_sentence: orNull(example),
      personal_sentence: orNull(personal),
      sentence_pattern: isVerb ? orNull(pattern) : null,
      verb_forms: isVerb ? verb : null,
      chapter_id: chapterId,
      source: orNull(source),
    });
  }

  const articleChips = (
    <View style={styles.group}>
      <Text style={styles.label}>Article</Text>
      <ArticleButtons
        label="Article"
        state={(a) => (a === article ? "selected" : "idle")}
        onPick={setArticle}
      />
    </View>
  );
  const pluralFields = (
    <>
      <View style={styles.switchRow}>
        <Text style={styles.label}>Plural only (like die Eltern)</Text>
        <Switch
          value={pluralOnly}
          onValueChange={setPluralOnly}
          trackColor={{ false: colors.border, true: colors.primary }}
          thumbColor={pluralOnly ? colors.onPrimary : colors.background}
        />
      </View>
      {!pluralOnly && (
        <Field label="Plural" value={plural} onChangeText={setPlural} placeholder="die …" />
      )}
    </>
  );
  const verbFields = (
    <View style={styles.group}>
      <Text style={styles.label}>Present tense</Text>
      {PERSONS.map((p) => (
        <View key={p.key} style={styles.personRow}>
          <Text style={styles.person}>{p.label}</Text>
          <View style={styles.personInput}>
            <Field
              label=""
              accessibilityLabel={`Present tense, ${p.label}`}
              value={verb.present?.[p.key] ?? ""}
              onChangeText={(t) => setPresent(p.key, t)}
              autoCapitalize="none"
            />
          </View>
        </View>
      ))}
      <Field
        label="Past participle (Partizip II)"
        value={verb.past_participle ?? ""}
        onChangeText={(t) => setVerb((v) => ({ ...v, past_participle: t || null }))}
        autoCapitalize="none"
      />
      <Chips
        label="Perfekt with"
        options={AUXILIARIES}
        selected={verb.auxiliary ?? null}
        onSelect={(a) => setVerb((v) => ({ ...v, auxiliary: a }))}
      />
      <Field
        label="Common pattern"
        value={pattern}
        onChangeText={setPattern}
        placeholder="e.g. um 7 Uhr aufstehen"
      />
    </View>
  );
  const exampleField = (
    <View style={styles.group}>
      <Field
        label="Example sentence"
        value={example}
        onChangeText={setExample}
        multiline
        placeholder="From the book or class"
      />
      {exampleTranslation != null && example === initial.example_sentence && (
        <Text style={styles.muted}>= {exampleTranslation}</Text>
      )}
    </View>
  );
  const extras = (
    <>
      <Field label="Meaning (Urdu, optional)" value={meaningUr} onChangeText={setMeaningUr} />
      <Field
        label="My own sentence"
        value={personal}
        onChangeText={setPersonal}
        multiline
        placeholder="Write one about your life"
      />
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
      <Field label="Source" value={source} onChangeText={setSource} placeholder="e.g. S. 24" />
    </>
  );

  return (
    <FormScroll contentContainerStyle={styles.form}>
      {mode === "dictionary" && !editDetails ? (
        <Card glass>
          {summarize({
            kind,
            german,
            article,
            plural: plural || null,
            pluralOnly,
            verb: isVerb ? verb : null,
          }).map((line, i) => (
            <Text key={line} style={i === 0 ? styles.headword : styles.summaryLine}>
              {line}
            </Text>
          ))}
          {pronounce}
          <Text style={styles.muted}>Filled in from the dictionary.</Text>
          <TextLink label="Change these details" onPress={() => setEditDetails(true)} />
        </Card>
      ) : (
        <>
          <Chips
            label="Type"
            options={KINDS}
            selected={kind}
            onSelect={(k) => {
              setKind(k);
              setKindTouched(true);
            }}
          />
          <Field
            label="German"
            value={german}
            onChangeText={changeGerman}
            autoCapitalize="none"
            autoFocus={mode === "manual" && german.length === 0}
          />
          {pronounce}
          {isNoun && (mode === "edit" || editDetails) && (
            <>
              {!pluralOnly && articleChips}
              {mode !== "manual" && pluralFields}
            </>
          )}
          {isVerb && mode !== "manual" && verbFields}
        </>
      )}

      {suggestedMeanings.length > 1 && otherMeanings.length > 0 && (
        <View style={styles.group}>
          <Text style={styles.label}>Other meanings (tap to use)</Text>
          <View style={styles.suggestions}>
            {otherMeanings.map((m) => (
              <Pressable
                key={m}
                accessibilityRole="button"
                onPress={() => setMeaningEn(m)}
                android_ripple={{ color: colors.divider }}
                style={styles.suggestion}
              >
                <Text style={styles.suggestionText}>{m}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      )}
      <Field label="Meaning (English)" value={meaningEn} onChangeText={setMeaningEn} />

      {mode === "dictionary" && initial.example_sentence ? exampleField : null}
      {mode === "edit" && (
        <>
          {extras}
          {exampleField}
        </>
      )}

      {mode !== "edit" && (
        <>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ expanded: showMore }}
            onPress={() => setShowMore((s) => !s)}
            android_ripple={{ color: colors.divider }}
            style={styles.moreToggle}
          >
            <IconLabel trailing icon={showMore ? ChevronUp : ChevronDown} color={colors.primary} style={styles.link}>
              More details (optional)
            </IconLabel>
          </Pressable>
          {showMore && (
            <>
              {mode === "manual" && isNoun && pluralFields}
              {mode === "manual" && isVerb && verbFields}
              {(mode === "manual" || (mode === "dictionary" && !initial.example_sentence)) &&
                exampleField}
              {extras}
            </>
          )}
        </>
      )}

      {isNoun && !article && !pluralOnly && (
        <Text style={styles.muted}>Tip: add the article (der, die or das). It is part of the word.</Text>
      )}
      {error != null && <ErrorText error={error} />}
      <Button label={submitLabel} busy={busy} disabled={!valid} onPress={submit} />
    </FormScroll>
  );
}

const useStyles = makeStyles((colors) => ({
  form: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  group: { gap: space.sm },
  label: { fontSize: 14, lineHeight: 20, fontWeight: "600", color: colors.muted },
  switchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: TOUCH },
  moreToggle: { minHeight: TOUCH, justifyContent: "center", alignSelf: "flex-start" },
  personRow: { flexDirection: "row", alignItems: "flex-end", gap: space.md },
  person: { width: 72, paddingBottom: space.md, color: colors.text },
  personInput: { flex: 1 },
  suggestions: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  suggestion: {
    minHeight: TOUCH,
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primaryContainer,
    paddingHorizontal: space.lg,
    overflow: "hidden",
  },
  suggestionText: { color: colors.onPrimaryContainer, fontSize: 15, lineHeight: 22, fontWeight: "700" },
  headword: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  summaryLine: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  link: { color: colors.primary, fontSize: 15, lineHeight: 22, fontWeight: "700" },
}));
