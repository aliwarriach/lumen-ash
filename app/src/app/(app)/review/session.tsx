import { useQueryClient } from "@tanstack/react-query";
import { randomUUID } from "expo-crypto";
import { router } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { View } from "react-native";

import { ReviewCardView, type Outcome } from "@/features/review/ReviewCardView";
import {
  QUEUE_KEY,
  STAGE_EXPLANATIONS,
  useOutboxSync,
  useReviewQueue,
  type QueueCard,
} from "@/features/review/api";
import { enqueue } from "@/features/review/outbox";
import { STAGE_LABELS, headword } from "@/features/vocabulary/api";
import { Button, Card, Centered, ErrorText, Loading, ProgressBar } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Celebration } from "@/ui/Celebration";
import { Backdrop, Glass } from "@/ui/glass";
import { Text } from "@/ui/Text";
import { makeStyles, space } from "@/ui/theme";

type Step = { card: QueueCard; key: string };

export default function ReviewSession() {
  const styles = useStyles();
  const queue = useReviewQueue();
  if (!queue.data) {
    return (
      <Centered>
        {queue.isError ? (
          <View style={styles.problem}>
            <ErrorText error={queue.error} />
            <Text style={styles.muted}>
              Reviews you answered earlier are safe on this phone and upload when you are back
              online.
            </Text>
            <Button label="Try again" onPress={() => void queue.refetch()} />
            <Button label="Back" variant="secondary" onPress={() => router.back()} />
          </View>
        ) : (
          <Loading label="Getting today’s cards…" />
        )}
      </Centered>
    );
  }
  // The session works from a snapshot, so answering doesn't reshuffle cards mid-session.
  return <Session initial={queue.data.cards} />;
}

function Session({ initial }: { initial: QueueCard[] }) {
  const styles = useStyles();
  const queryClient = useQueryClient();
  const flush = useOutboxSync();
  const [steps, setSteps] = useState<Step[]>(() =>
    initial.map((card) => ({ card, key: card.card_id })),
  );
  const [index, setIndex] = useState(0);
  const [answered, setAnswered] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [news, setNews] = useState<string[]>([]);
  const shownAt = useRef(0);

  useEffect(() => {
    shownAt.current = Date.now(); // when this card appeared, for answer timing
  }, [index]);

  const current = steps[index];

  async function finish() {
    await flush();
    await queryClient.invalidateQueries({ queryKey: QUEUE_KEY });
    router.back();
  }

  if (!current) {
    return (
      <Backdrop>
        <FormScroll contentContainerStyle={styles.page}>
          <Glass>
            {answered > 0 && <Celebration />}
            <Text style={styles.big} accessibilityRole="header">
              Session done
            </Text>
            <Text style={styles.body}>
              {answered} answers · {answered ? Math.round((100 * correct) / answered) : 0}% right
            </Text>
          </Glass>
          {news.map((n) => (
            <Card key={n}>
              <Text style={styles.body}>{n}</Text>
            </Card>
          ))}
          <Button label="Done" onPress={() => void finish()} />
        </FormScroll>
      </Backdrop>
    );
  }

  async function onDone(outcome: Outcome) {
    const card = current!.card;
    await enqueue({
      id: randomUUID(),
      card_id: card.card_id,
      rating: outcome.rating,
      answer: outcome.answer,
      reviewed_at: new Date().toISOString(),
      duration_ms: Math.min(Date.now() - shownAt.current, 3_600_000),
    });
    setAnswered((n) => n + 1);
    if (outcome.correct) setCorrect((n) => n + 1);
    // Missed cards come back at the end of this session, as FSRS reschedules them in minutes.
    if (outcome.rating === 1) {
      setSteps((s) => [...s, { card, key: `${card.card_id}-${s.length}` }]);
    }
    setIndex((i) => i + 1);

    // Upload in the background; tell the learner when a word moves to a new stage.
    void flush().then((result) => {
      const messages = result.sent.flatMap((r) => {
        if (!r.stage_changed || !r.stage) return [];
        const word = steps.find((s) => s.card.word && s.card.word.id === r.word_id)?.card.word;
        const name = word ? headword(word) : "A word";
        return [`${name} is now ${STAGE_LABELS[r.stage]}. ${STAGE_EXPLANATIONS[r.stage]}`];
      });
      const refused = result.rejected.map((r) => `One answer wasn't saved: ${r.message}`);
      if (messages.length || refused.length) setNews((n) => [...n, ...messages, ...refused]);
    });
  }

  return (
    <Backdrop>
      <FormScroll contentContainerStyle={styles.page}>
        <View style={styles.progress}>
          <ProgressBar value={index / steps.length} label="Session progress" />
          <Text style={styles.muted}>
            {index + 1} / {steps.length}
            {current.card.card_type === "error_retry"
              ? " · mistake"
              : current.card.is_new
                ? " · new"
                : ""}
          </Text>
        </View>
        <Glass>
          <ReviewCardView key={current.key} card={current.card} onDone={(o) => void onDone(o)} />
        </Glass>
      </FormScroll>
    </Backdrop>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { padding: space.lg, gap: space.lg },
  progress: { gap: space.xs },
  problem: { gap: space.md, alignSelf: "stretch" },
  big: { fontSize: 26, lineHeight: 34, fontWeight: "800" },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
}));
