import { View } from "react-native";

import { BookA, BookOpen, ClipboardList, ICON, PenLine, SpellCheck, type Icon } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, space, useTheme } from "@/ui/theme";

import { KIND_LABELS, describe, type Attachment, type AttachmentKind } from "./ask";

const KIND_ICONS: Record<AttachmentKind, Icon> = {
  word: BookA,
  exercise: PenLine,
  lesson: BookOpen,
  grammar: SpellCheck,
  resource: ClipboardList,
};

/**
 * The shared item above a question in the chat (and in the "Ask the Community" sheet): what kind
 * it is, its title and a few lines. Read out as one sentence.
 */
export function AttachmentCard({ attachment: a }: { attachment: Attachment }) {
  const styles = useStyles();
  const colors = useTheme();
  const KindIcon = KIND_ICONS[a.kind];
  return (
    <View style={styles.card} accessible accessibilityLabel={describe(a)}>
      <View style={styles.kindRow}>
        <KindIcon size={ICON.small} color={colors.onPrimaryContainer} />
        <Text style={styles.kind}>{KIND_LABELS[a.kind].toUpperCase()}</Text>
      </View>
      <Text style={styles.title}>{a.title}</Text>
      {(a.lines ?? []).map((line, i) => (
        <Text key={i} style={styles.line}>
          {line}
        </Text>
      ))}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  card: {
    gap: 2,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    backgroundColor: colors.well,
    borderRadius: 12,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    marginBottom: space.xs,
  },
  kindRow: { flexDirection: "row", alignItems: "center", gap: space.xs },
  kind: { fontSize: 13, lineHeight: 18, fontWeight: "800", letterSpacing: 0.4, color: colors.onPrimaryContainer },
  title: { fontSize: 16, lineHeight: 22, fontWeight: "800" },
  line: { fontSize: 14, lineHeight: 20, color: colors.muted },
}));
