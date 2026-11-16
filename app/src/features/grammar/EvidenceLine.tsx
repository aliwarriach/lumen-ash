
import type { Evidence } from "@/features/grammar/api";
import { shortDate } from "@/features/mistakes/MistakeRow";
import { Check, ICON, X } from "@/ui/icons";
import { IconLabel } from "@/ui/components";
import { Text } from "@/ui/Text";
import { makeStyles, useTheme } from "@/ui/theme";

/** One right or wrong answer behind a grammar statistic: (✗ icon) "das Tisch → der Tisch". */
export function EvidenceLine({ evidence: e }: { evidence: Evidence }) {
  const colors = useTheme();
  const styles = useStyles();
  return (
    <IconLabel
      icon={e.correct ? Check : X}
      size={ICON.small}
      color={e.correct ? colors.success : colors.danger}
      style={styles.line}
    >
      {e.given ?? "(no answer)"}
      {!e.correct && e.expected ? <Text style={styles.right}>{`  →  ${e.expected}`}</Text> : null}
      <Text style={styles.meta}>{`   ${e.label}, ${shortDate(e.occurred_at)}`}</Text>
    </IconLabel>
  );
}

const useStyles = makeStyles((colors) => ({
  line: { fontSize: 15, color: colors.text },
  right: { color: colors.success, fontWeight: "600" },
  wrong: { color: colors.danger, fontWeight: "600" },
  meta: { fontSize: 13, color: colors.muted },
}));
