import { router } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";

import { remainingText, useAiQuota } from "@/features/ai/api";
import {
  LABEL_COLORS,
  LABEL_TEXT,
  useCheckWriting,
  type CheckResult,
  type Correction,
} from "@/features/coach/api";
import { CheckResultView } from "@/features/coach/CheckResultView";
import { AskCommunityButton } from "@/features/community/AskCommunity";
import { aboutScannedItem } from "@/features/community/ask";
import {
  ANSWER_LABEL_HELP,
  useExerciseHelp,
  type ExerciseHelp,
  type ExerciseItem,
} from "@/features/scanner/api";
import { choosePhoto, pendingPhoto, takePhoto, type PhotoResult } from "@/features/scanner/photo";
import { MAX_EXERCISE_CHARS, canSend, forSending, reviewNote } from "@/features/scanner/text";
import { Button, Card, ErrorText, Field, IconLabel, Pill, TextLink } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { ArrowRight, Lightbulb } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, space, toneAccent, useTheme } from "@/ui/theme";

type Step = "start" | "review" | "result";

export default function Scanner() {
  const styles = useStyles();
  const quota = useAiQuota();
  const help = useExerciseHelp();
  const [step, setStep] = useState<Step>("start");
  const [text, setText] = useState("");
  const [fromPhoto, setFromPhoto] = useState(false);
  const [reading, setReading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const left = quota.data?.features.find((f) => f.feature === "exercise_help");

  function received(result: PhotoResult) {
    setReading(false);
    if (result.kind === "text") {
      setText(result.text);
      setFromPhoto(true);
      setProblem(null);
      setStep("review");
    } else if (result.kind === "failed") {
      setProblem(result.message);
    }
  }

  async function read(source: () => Promise<PhotoResult>) {
    setReading(true);
    setProblem(null);
    try {
      received(await source());
    } catch {
      received({ kind: "failed", message: "Something went wrong with the camera. Please try again." });
    }
  }

  // Android may have closed the app while the camera was open: pick the photo up again.
  useEffect(() => {
    pendingPhoto()
      .then((result) => result && received(result))
      .catch(() => undefined);
  }, []);

  function startAgain() {
    help.reset();
    setText("");
    setFromPhoto(false);
    setProblem(null);
    setStep("start");
  }

  if (step === "result" && help.data) {
    return <Result help={help.data} onAgain={startAgain} onEdit={() => setStep("review")} />;
  }

  if (step === "review") {
    const note = reviewNote(text);
    return (
      <FormScroll contentContainerStyle={styles.page}>
        <Card glass>
          <Text style={styles.heading}>Check the text</Text>
          <Text style={styles.muted}>
            {fromPhoto
              ? "This is what the phone read, with the usual misreads already tidied (ß, Ich, gaps, words split over two lines). Fix what is still wrong, put missing gaps (___) back and delete any names: only this text is sent, and the photo is already gone."
              : "Type or paste one exercise. Write each gap as ___ and leave out any names: only this text is sent."}
          </Text>
        </Card>
        <Field
          label="Exercise"
          value={text}
          onChangeText={setText}
          multiline
          numberOfLines={10}
          maxLength={MAX_EXERCISE_CHARS + 200}
          style={styles.textArea}
          textAlignVertical="top"
          autoCapitalize="none"
        />
        {note && (
          <Text style={[styles.note, note.severity === "warning" && styles.warning]}>{note.text}</Text>
        )}
        <Text style={styles.muted}>{left ? remainingText(left) : ""}</Text>
        <Button
          label="Get hints and answers"
          busy={help.isPending}
          disabled={!canSend(text)}
          onPress={() =>
            help.mutate(forSending(text), {
              onSuccess: () => setStep("result"),
            })
          }
        />
        {help.isPending && (
          <Text style={styles.muted}>
            Working it out. The first request of the day can take a minute while the server wakes.
          </Text>
        )}
        {help.isError && <ErrorText error={help.error} />}
        <Button label="Start again" variant="secondary" onPress={startAgain} />
      </FormScroll>
    );
  }

  return (
    <FormScroll contentContainerStyle={styles.page}>
      <Card glass>
        <Text style={styles.heading}>Scan an exercise</Text>
        <Text style={styles.muted}>
          Photograph one exercise from your book or worksheet. The phone reads the text itself: the
          photo is never uploaded or kept. You check the text, then get a hint for each item, and
          the answer only when you ask.
        </Text>
        <Text style={styles.muted}>
          Works best with printed text in good light. Pictures, listening tasks and layouts such as
          matching columns only partly come through as text, and the app says so rather than guess.
        </Text>
      </Card>
      <Button label="Take a photo" busy={reading} onPress={() => read(takePhoto)} />
      <Button
        label="Choose a photo"
        variant="secondary"
        disabled={reading}
        onPress={() => read(choosePhoto)}
      />
      <Button
        label="Type or paste the exercise"
        variant="secondary"
        disabled={reading}
        onPress={() => setStep("review")}
      />
      {reading && <Text style={styles.muted}>Reading the photo…</Text>}
      {problem && <Text accessibilityLiveRegion="polite" style={[styles.note, styles.warning]}>{problem}</Text>}
    </FormScroll>
  );
}

function Result({
  help,
  onAgain,
  onEdit,
}: {
  help: ExerciseHelp;
  onAgain: () => void;
  onEdit: () => void;
}) {
  const styles = useStyles();
  const names = { ai: "the AI", languagetool: "LanguageTool" } as const;
  return (
    <FormScroll contentContainerStyle={styles.page}>
      {help.instruction && (
        <Card glass>
          <Text style={styles.heading}>The exercise</Text>
          <Text style={styles.body}>{help.instruction}</Text>
        </Card>
      )}
      <Text style={styles.muted}>
        Answers by {help.checked_by.map((c) => names[c]).join(", checked by ")}.
        {help.checked_by.includes("languagetool")
          ? ""
          : " LanguageTool wasn't available, so nothing could be confirmed."}
        {help.cached ? " (Asked before: no allowance used.)" : ""}
      </Text>
      {help.limits && <Text style={[styles.note, styles.warning]}>{help.limits}</Text>}
      {help.items.map((item, i) => (
        <ItemCard key={`${item.number}-${i}`} item={item} instruction={help.instruction} />
      ))}
      <Button label="Fix the text and ask again" variant="secondary" onPress={onEdit} />
      <Button label="Scan another exercise" onPress={onAgain} />
    </FormScroll>
  );
}

function ItemCard({ item, instruction }: { item: ExerciseItem; instruction: string | null }) {
  const styles = useStyles();
  const colors = useTheme();
  const [hint, setHint] = useState(false);
  const [answer, setAnswer] = useState(false);
  const [attempt, setAttempt] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const check = useCheckWriting();

  // A decision changes one correction: keep the rest of the result as it is.
  function updated(c: Correction) {
    setResult((r) => r && { ...r, corrections: r.corrections.map((x) => (x.id === c.id ? c : x)) });
  }

  return (
    <Card>
      <Text style={styles.body}>
        {item.number ? `${item.number}  ` : ""}
        {item.task}
      </Text>
      <AskCommunityButton
        attachment={() => aboutScannedItem(instruction, item, attempt.trim() || null)}
      />

      {hint ? (
        <View style={styles.hint}>
          <IconLabel icon={Lightbulb} color={colors.amber.fg} style={styles.hintText}>
            {item.hint}
          </IconLabel>
        </View>
      ) : (
        <Button label="Show hint" variant="secondary" onPress={() => setHint(true)} />
      )}

      <Field
        label="Try it yourself: write the whole sentence"
        value={attempt}
        onChangeText={setAttempt}
        multiline
        maxLength={600}
        autoCapitalize="sentences"
      />
      <Button
        label="Check my sentence"
        variant="secondary"
        busy={check.isPending}
        disabled={!attempt.trim()}
        onPress={() => check.mutate({ text: attempt.trim() }, { onSuccess: setResult })}
      />
      {check.isError && <ErrorText error={check.error} />}
      {result && <CheckResultView result={result} onDecided={updated} />}

      {answer ? (
        <View style={styles.answer}>
          <View style={styles.row}>
            <Pill label={LABEL_TEXT[item.label]} accent={toneAccent(colors, LABEL_COLORS[item.label])} />
            <Text style={styles.muted}>{ANSWER_LABEL_HELP[item.label]}</Text>
          </View>
          <Text style={styles.answerText}>{item.answer}</Text>
          {item.filled && item.filled !== item.answer && <Text style={styles.body}>{item.filled}</Text>}
          {item.why && <Text style={styles.body}>{item.why}</Text>}
          {item.verified_by && <Text style={styles.muted}>{item.verified_by}</Text>}
          {item.warning && <Text style={[styles.warning, { color: colors.warning }]}>{item.warning}</Text>}
          {item.pattern_key && (
            <TextLink
              label={`Review: ${item.pattern_title}`}
              icon={ArrowRight}
              onPress={() =>
                router.push({ pathname: "/grammar/[key]", params: { key: item.pattern_key! } })
              }
            />
          )}
        </View>
      ) : (
        <Button label="Show answer" onPress={() => setAnswer(true)} />
      )}
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  heading: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  note: { fontSize: 14, lineHeight: 20, color: colors.muted },
  warning: { color: colors.warning, fontWeight: "600" },
  textArea: { minHeight: 200 },
  hint: { backgroundColor: colors.amber.bg, padding: space.lg, borderRadius: 18 },
  hintText: { fontSize: 15, lineHeight: 22, color: colors.text },
  row: { gap: space.xs },
  answer: { gap: space.sm },
  answerText: { fontSize: 17, lineHeight: 24, color: colors.success, fontWeight: "700" },
}));
