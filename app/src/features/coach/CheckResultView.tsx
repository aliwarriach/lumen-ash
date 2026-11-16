import { router } from "expo-router";
import { View } from "react-native";

import {
  LABEL_COLORS,
  LABEL_HELP,
  LABEL_TEXT,
  useDecide,
  type CheckResult,
  type Correction,
  type Decision,
} from "@/features/coach/api";
import { Check } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { Button, Card, ErrorText, IconLabel } from "@/ui/components";
import { makeStyles, radius, space, useTheme } from "@/ui/theme";

/** The result of a sentence check: each correction to accept, reject or flag, then the rest. */
export function CheckResultView({
  result,
  onDecided,
}: {
  result: CheckResult;
  onDecided: (c: Correction) => void;
}) {
  const colors = useTheme();
  const styles = useStyles();
  const names = { languagetool: "LanguageTool", ai: "AI" } as const;
  const checkedBy = result.checked_by.map((c) => names[c]).join(" and ");
  return (
    <View style={styles.result}>
      <Text style={styles.muted}>Checked with {checkedBy}.</Text>
      {result.ai_message && <Text style={styles.note}>{result.ai_message}</Text>}
      {result.redacted && (
        <Text style={styles.note}>Names and phone numbers were hidden before checking.</Text>
      )}
      {result.task_done && (
        <IconLabel icon={Check} color={colors.success} style={styles.done}>
          Writing task done
        </IconLabel>
      )}

      {result.corrections.length === 0 ? (
        <Card>
          <Text style={styles.body}>No mistakes found.</Text>
          <Text style={styles.muted}>
            That does not guarantee the text is perfect: ask your teacher if you are unsure.
          </Text>
        </Card>
      ) : (
        result.corrections.map((c) => <CorrectionCard key={c.id} c={c} onDecided={onDecided} />)
      )}

      {result.suggested_text && (
        <Card>
          <Text style={styles.heading}>Corrected text</Text>
          <Text style={styles.body}>{result.suggested_text}</Text>
        </Card>
      )}
      {result.explanation && (
        <Card>
          <Text style={styles.heading}>Explanation</Text>
          <Text style={styles.body}>{result.explanation}</Text>
        </Card>
      )}
      {result.practice.length > 0 && (
        <Card>
          <Text style={styles.heading}>Practice</Text>
          {result.practice.map((p) => (
            <Text key={p} style={styles.body}>
              • {p}
            </Text>
          ))}
        </Card>
      )}
    </View>
  );
}

function CorrectionCard({ c, onDecided }: { c: Correction; onDecided: (c: Correction) => void }) {
  const styles = useStyles();
  const colors = useTheme();
  const decide = useDecide();
  const color = colors[LABEL_COLORS[c.label]];
  const choose = (decision: Decision) => decide.mutate({ id: c.id, decision }, { onSuccess: onDecided });
  const pending = c.status === "pending" || c.status === "flagged";

  return (
    <Card>
      <View style={styles.row}>
        <Text style={[styles.badge, { color, borderColor: color }]}>{LABEL_TEXT[c.label]}</Text>
        <Text style={styles.muted}>{LABEL_HELP[c.label]}</Text>
      </View>
      <Text style={styles.body}>
        <Text style={styles.wrong}>{c.wrong}</Text> → <Text style={styles.right}>{c.correct}</Text>
      </Text>
      {c.alternatives.length > 0 && (
        <Text style={styles.muted}>Other possibilities: {c.alternatives.join(", ")}</Text>
      )}
      {c.explanation && <Text style={styles.body}>{c.explanation}</Text>}
      {c.warning && <Text style={[styles.warning, { color: colors.warning }]}>{c.warning}</Text>}
      {c.pattern_key && (
        <Text
          style={styles.link}
          onPress={() => router.push({ pathname: "/grammar/[key]", params: { key: c.pattern_key! } })}
        >
          Review: {c.pattern_title}
        </Text>
      )}

      {pending ? (
        <View style={styles.actions}>
          <Button label="Accept" busy={decide.isPending} onPress={() => choose("accept")} />
          <Button label="Reject" variant="secondary" onPress={() => choose("reject")} />
          {c.status !== "flagged" && (
            <Button label="Flag" variant="secondary" onPress={() => choose("flag")} />
          )}
        </View>
      ) : (
        <Text style={styles.muted}>
          {c.status === "accepted"
            ? "Accepted: added to your mistake log."
            : "Rejected: not added to your mistake log."}
        </Text>
      )}
      {c.status === "flagged" && <Text style={styles.muted}>Flagged: bring this to your teacher.</Text>}
      {decide.isError && <ErrorText error={decide.error} />}
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  heading: { fontSize: 13, color: colors.muted },
  body: { fontSize: 16, color: colors.text },
  muted: { fontSize: 13, color: colors.muted },
  note: { fontSize: 13, color: colors.warning },
  done: { fontSize: 16, color: colors.success, fontWeight: "600" },
  result: { gap: space.md },
  row: { gap: space.xs },
  badge: {
    alignSelf: "flex-start",
    fontSize: 13,
    fontWeight: "600",
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
  },
  wrong: { color: colors.danger, textDecorationLine: "line-through" },
  right: { color: colors.success, fontWeight: "600" },
  warning: { fontSize: 14, fontWeight: "600" },
  link: { fontSize: 14, color: colors.primary },
  actions: { gap: space.sm, marginTop: space.sm },
}));
