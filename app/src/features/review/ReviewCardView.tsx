import { useState } from "react";
import { Pressable, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";

import type { QueueCard } from "@/features/review/api";
import {
  checkArticle,
  checkCorrection,
  checkProduce,
  usesWord,
  type Grade,
} from "@/features/review/grading";
import type { ReviewIn } from "@/features/review/outbox";
import { ArticleButtons, type ButtonState } from "@/features/vocabulary/ArticleButtons";
import { PronounceButton } from "@/features/vocabulary/PronounceButton";
import { headword } from "@/features/vocabulary/api";
import { Check, X } from "@/ui/icons";
import { useReduceMotion } from "@/ui/motion";
import { Text } from "@/ui/Text";
import { Button, Field, IconLabel } from "@/ui/components";
import { makeStyles, space, TOUCH, useTheme, type Accent, type Palette } from "@/ui/theme";

export type Outcome = { rating: 1 | 2 | 3 | 4; correct: boolean; answer: ReviewIn["answer"] };
type OnDone = (outcome: Outcome) => void;
type Props = { card: QueueCard; onDone: OnDone };
type WordProps = { word: NonNullable<QueueCard["word"]>; onDone: OnDone };
type MistakeProps = { mistake: NonNullable<QueueCard["mistake"]>; onDone: OnDone };

const SELF_RATINGS = [
  { rating: 1, label: "Again", hint: "Didn't know" },
  { rating: 2, label: "Hard", hint: "With effort" },
  { rating: 3, label: "Good", hint: "Knew it" },
  { rating: 4, label: "Easy", hint: "Instantly" },
] as const;

/** How well it went, in a tint each: Again (red), Hard (orange), Good (green), Easy (indigo). The words say it too. */
const RATING_TONE: Record<1 | 2 | 3 | 4, (colors: Palette) => Accent> = {
  1: (c) => ({ fg: c.wrong.fg, bg: c.wrong.bg }),
  2: (c) => c.orange,
  3: (c) => c.green,
  4: (c) => ({ fg: c.onPrimaryContainer, bg: c.primaryContainer }),
};

export function ReviewCardView({ card, onDone }: Props) {
  if (card.card_type === "error_retry") {
    return card.mistake ? <ErrorRetryCard mistake={card.mistake} onDone={onDone} /> : null;
  }
  const word = card.word;
  if (!word) return null;
  switch (card.card_type) {
    case "recall":
      return <RecallCard word={word} onDone={onDone} />;
    case "produce":
      return <ProduceCard word={word} onDone={onDone} />;
    case "article":
      return <ArticleCard word={word} onDone={onDone} />;
    case "sentence":
      return <SentenceCard word={word} onDone={onDone} />;
  }
}

/** German shown; the learner recalls the meaning and rates themselves. */
function RecallCard({ word: w, onDone }: WordProps) {
  const styles = useStyles();
  const [shown, setShown] = useState(false);
  return (
    <View style={styles.card}>
      <Text style={styles.prompt}>What does this mean?</Text>
      <Text style={styles.headword}>{headword(w)}</Text>
      <View style={styles.speak}>
        <PronounceButton text={headword(w)} audioUrl={w.audio_url} />
      </View>
      {shown ? (
        <>
          <Answer word={w} />
          <Ratings
            options={SELF_RATINGS}
            onRate={(rating) => onDone({ rating, correct: rating > 1, answer: {} })}
          />
        </>
      ) : (
        <Button label="Show answer" onPress={() => setShown(true)} />
      )}
    </View>
  );
}

/** English shown; the learner types the German. Checked automatically. */
function ProduceCard({ word: w, onDone }: WordProps) {
  const styles = useStyles();
  const [text, setText] = useState("");
  const [grade, setGrade] = useState<Grade | null>(null);
  const hint =
    w.kind === "noun" ? "Include the article (der, die, das)." : w.kind === "verb" ? "Infinitive." : null;

  return (
    <View style={styles.card}>
      <Text style={styles.prompt}>Say it in German</Text>
      <Text style={styles.headword}>{w.meaning_en}</Text>
      {hint && <Text style={styles.muted}>{hint}</Text>}
      <Field
        label=""
        accessibilityLabel="Your answer in German"
        value={text}
        onChangeText={setText}
        editable={!grade}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="Type the German"
        onSubmitEditing={() => text.trim() && setGrade(checkProduce(w, text))}
      />
      {grade ? (
        <Checked
          grade={grade}
          speak={<PronounceButton text={grade.expected} audioUrl={w.audio_url} />}
          onDone={(rating) => onDone({ rating, correct: grade.correct, answer: { text } })}
        />
      ) : (
        <View style={styles.row}>
          <Button
            label="I don't know"
            variant="secondary"
            onPress={() => setGrade(checkProduce(w, ""))}
          />
          <Button
            label="Check"
            disabled={!text.trim()}
            onPress={() => setGrade(checkProduce(w, text))}
          />
        </View>
      )}
    </View>
  );
}

/** Nouns: pick the article and type the plural. Checked automatically. */
function ArticleCard({ word: w, onDone }: WordProps) {
  const styles = useStyles();
  const asksPlural = Boolean(w.plural) && !w.plural_only;
  const [article, setArticle] = useState<"der" | "die" | "das" | null>(null);
  const [plural, setPlural] = useState("");
  const [grade, setGrade] = useState<Grade | null>(null);

  return (
    <View style={styles.card}>
      <Text style={styles.prompt}>
        {asksPlural ? "Article and plural" : w.plural_only ? "Article (plural only)" : "Article"}
      </Text>
      <Text style={styles.headword}>{w.german}</Text>
      <Text style={styles.muted}>{w.meaning_en}</Text>
      <ArticleButtons
        label="Choose the article"
        state={(a): ButtonState =>
          grade
            ? a === w.article
              ? "right"
              : a === article
                ? "wrong"
                : "idle"
            : a === article
              ? "selected"
              : "idle"
        }
        onPick={(a) => !grade && setArticle(a)}
      />
      {asksPlural && (
        <Field
          label="Plural: die …"
          value={plural}
          onChangeText={setPlural}
          editable={!grade}
          autoCapitalize="none"
          autoCorrect={false}
        />
      )}
      {grade ? (
        <Checked
          grade={grade}
          onDone={(rating) =>
            onDone({
              rating,
              correct: grade.correct,
              answer: { article, plural: asksPlural ? plural : null },
            })
          }
        />
      ) : (
        <Button
          label="Check"
          disabled={!article || (asksPlural && !plural.trim())}
          onPress={() => setGrade(checkArticle(w, article, plural))}
        />
      )}
    </View>
  );
}

/** The learner writes their own sentence and judges it (automatic checking comes later). */
function SentenceCard({ word: w, onDone }: WordProps) {
  const styles = useStyles();
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function submit() {
    if (!usesWord(w, text)) {
      setProblem(`Use "${w.german}" (or one of its forms) in your sentence.`);
      return;
    }
    setProblem(null);
    setSubmitted(true);
  }

  return (
    <View style={styles.card}>
      <Text style={styles.prompt}>Write your own sentence with</Text>
      <Text style={styles.headword}>{headword(w)}</Text>
      <Text style={styles.muted}>{w.meaning_en}</Text>
      <Field
        label=""
        accessibilityLabel="Your sentence"
        value={text}
        onChangeText={setText}
        editable={!submitted}
        multiline
        placeholder="Ich …"
        style={{ minHeight: 80, textAlignVertical: "top" }}
      />
      {problem && <Text style={styles.wrong}>{problem}</Text>}
      {submitted ? (
        <>
          <Text style={styles.muted}>
            Is your sentence correct? Automatic checking comes later; for now compare it with your
            book, or ask your teacher.
          </Text>
          <Ratings
            options={[
              { rating: 1, label: "Not right", hint: "" },
              { rating: 2, label: "Unsure", hint: "" },
              { rating: 3, label: "Correct", hint: "" },
              { rating: 4, label: "Easy", hint: "" },
            ]}
            onRate={(rating) => onDone({ rating, correct: rating >= 3, answer: { text } })}
          />
        </>
      ) : (
        <Button label="Done" disabled={!text.trim()} onPress={submit} />
      )}
    </View>
  );
}

/** A logged mistake: the learner rewrites it correctly. Checked automatically. */
function ErrorRetryCard({ mistake, onDone }: MistakeProps) {
  const styles = useStyles();
  // Starts from the wrong version, so fixing it is an edit, as it would be on paper.
  const [text, setText] = useState(mistake.wrong);
  const [grade, setGrade] = useState<Grade | null>(null);
  const check = () => setGrade(checkCorrection(mistake.correct, text));
  // Giving up submits the mistake unchanged, which the server marks wrong.
  const giveUp = () => {
    setText(mistake.wrong);
    setGrade(checkCorrection(mistake.correct, mistake.wrong));
  };

  return (
    <View style={styles.card}>
      <Text style={styles.prompt}>Fix your mistake</Text>
      <Text style={styles.mistake}>{mistake.wrong}</Text>
      {mistake.pattern_title && <Text style={styles.muted}>Rule: {mistake.pattern_title}</Text>}
      <Field
        label=""
        accessibilityLabel="Your corrected sentence"
        value={text}
        onChangeText={setText}
        editable={!grade}
        multiline
        autoCorrect={false}
        style={{ minHeight: 64, textAlignVertical: "top" }}
      />
      {grade ? (
        <>
          {mistake.explanation && <Text style={styles.body}>{mistake.explanation}</Text>}
          <Checked
            grade={grade}
            onDone={(rating) => onDone({ rating, correct: grade.correct, answer: { text } })}
          />
        </>
      ) : (
        <View style={styles.row}>
          <Button
            label="Show me"
            variant="secondary"
            onPress={giveUp}
          />
          <Button label="Check" disabled={!text.trim()} onPress={check} />
        </View>
      )}
    </View>
  );
}

function Answer({ word }: { word: NonNullable<QueueCard["word"]> }) {
  const styles = useStyles();
  return (
    <View style={styles.answer}>
      <Text style={styles.meaning}>{word.meaning_en}</Text>
      {word.meaning_ur && <Text style={styles.meaning}>{word.meaning_ur}</Text>}
      {word.kind === "noun" && word.plural && <Text style={styles.muted}>die {word.plural}</Text>}
      {word.example_sentence && <Text style={styles.example}>{word.example_sentence}</Text>}
    </View>
  );
}

/** After a checked answer: right -> rate how easy it was; wrong -> it comes back soon. */
function Checked({
  grade,
  speak,
  onDone,
}: {
  grade: Grade;
  speak?: React.ReactNode;
  onDone: (rating: 1 | 2 | 3 | 4) => void;
}) {
  const colors = useTheme();
  const styles = useStyles();
  const reduce = useReduceMotion();
  const tone = grade.correct ? colors.right : colors.wrong;
  return (
    <View style={styles.answer}>
      <Animated.View
        entering={reduce ? undefined : FadeInDown.duration(160)}
        style={[styles.feedback, { backgroundColor: tone.bg }]}
        accessibilityLiveRegion="polite"
      >
        <IconLabel
          icon={grade.correct ? Check : X}
          color={tone.fg}
          style={[styles.feedbackTitle, { color: tone.fg }]}
        >
          {grade.correct ? "Richtig!" : "Not quite"}
        </IconLabel>
        <Text style={styles.feedbackLine}>{grade.expected}</Text>
        {grade.feedback && <Text style={styles.body}>{grade.feedback}</Text>}
      </Animated.View>
      {speak}
      {grade.correct ? (
        <Ratings options={SELF_RATINGS.slice(1)} onRate={onDone} />
      ) : (
        <Button label="Continue" onPress={() => onDone(1)} />
      )}
    </View>
  );
}

function Ratings({
  options,
  onRate,
}: {
  options: readonly { rating: 1 | 2 | 3 | 4; label: string; hint: string }[];
  onRate: (rating: 1 | 2 | 3 | 4) => void;
}) {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <View style={styles.ratings}>
      {options.map((o) => {
        const tone = RATING_TONE[o.rating](colors);
        return (
          <Pressable
            key={o.rating}
            accessibilityRole="button"
            accessibilityLabel={o.hint ? `${o.label}: ${o.hint}` : o.label}
            onPress={() => onRate(o.rating)}
            android_ripple={{ color: tone.fg + "33" }}
            style={[styles.rating, { backgroundColor: tone.bg }]}
          >
            <Text style={[styles.ratingLabel, { color: tone.fg }]}>{o.label}</Text>
            {o.hint ? <Text style={[styles.ratingHint, { color: tone.fg }]}>{o.hint}</Text> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  card: { gap: space.lg },
  prompt: { fontSize: 13, lineHeight: 18, fontWeight: "800", color: colors.muted, letterSpacing: 0.4, textTransform: "uppercase" },
  headword: { fontSize: 34, lineHeight: 42, fontWeight: "800", textAlign: "center" },
  speak: { alignItems: "center" },
  mistake: {
    fontSize: 22,
    lineHeight: 30,
    fontWeight: "600",
    color: colors.danger,
    textDecorationLine: "line-through",
    textDecorationColor: colors.danger,
  },
  meaning: { fontSize: 22, lineHeight: 30, fontWeight: "700", textAlign: "center" },
  example: { fontSize: 15, lineHeight: 22, color: colors.muted, fontStyle: "italic", textAlign: "center" },
  body: { fontSize: 15, lineHeight: 22 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  answer: { gap: space.md },
  feedback: { gap: space.xs, paddingVertical: 14, paddingHorizontal: space.lg, borderRadius: 18 },
  feedbackTitle: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  feedbackLine: { fontSize: 17, lineHeight: 24, fontWeight: "600" },
  wrong: { fontSize: 15, lineHeight: 22, fontWeight: "700", color: colors.danger },
  row: { flexDirection: "row", gap: space.md, justifyContent: "flex-end" },
  ratings: { flexDirection: "row", gap: space.sm },
  rating: {
    flex: 1,
    minHeight: TOUCH + 8,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: space.md,
    paddingHorizontal: space.xs,
    borderRadius: 16,
    overflow: "hidden",
  },
  ratingLabel: { fontSize: 15, lineHeight: 20, fontWeight: "800", textAlign: "center" },
  ratingHint: { fontSize: 13, lineHeight: 18, textAlign: "center" },
}));
