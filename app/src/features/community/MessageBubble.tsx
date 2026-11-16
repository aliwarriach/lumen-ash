import { memo } from "react";
import { Pressable, View } from "react-native";

import { Text } from "@/ui/Text";
import { makeStyles, radius, space, useTheme } from "@/ui/theme";

import { describe } from "./ask";
import { AttachmentCard } from "./AttachmentCard";
import { authorColor, timeLabel } from "./rows";
import type { ChatItem } from "./store";

type Props = {
  item: ChatItem;
  mine: boolean;
  /** Long press (or the screen reader's actions menu): reply, share, delete. */
  onLongPress: (item: ChatItem) => void;
  /** Tap on a message that was not sent. */
  onPressFailed: (item: ChatItem) => void;
};

/** One message. Own messages sit on the right; unsent ones are dimmed, failed ones say so. */
export const MessageBubble = memo(function MessageBubble({ item, mine, onLongPress, onPressFailed }: Props) {
  const styles = useStyles();
  const colors = useTheme();
  const failed = item.status === "failed";
  const sending = item.status === "sending";
  const who = mine ? "You" : item.authorName;
  const summary = item.deleted
    ? "message deleted"
    : item.attachment
      ? `${describe(item.attachment)}. ${item.body}`
      : item.body;

  return (
    <View style={[styles.row, mine ? styles.rowMine : styles.rowTheirs]}>
      <Pressable
        accessibilityLabel={`${who}, ${timeLabel(item.createdAt)}: ${summary}${failed ? ". Not sent. Double tap to try again." : ""}`}
        accessibilityHint={failed || item.deleted ? undefined : "Hold for reply and other actions"}
        onPress={failed ? () => onPressFailed(item) : undefined}
        onLongPress={item.status === "sent" && !item.deleted ? () => onLongPress(item) : undefined}
        delayLongPress={350}
        style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleTheirs, sending && styles.dim, failed && styles.failed]}
      >
        {!mine && (
          <Text style={[styles.name, { color: authorColor(item.authorId, colors.names) }]} numberOfLines={1}>
            {item.authorName}
          </Text>
        )}
        {item.reply && (
          <View style={styles.quote}>
            <Text style={styles.quoteName} numberOfLines={1}>
              {item.reply.authorName}
            </Text>
            <Text style={[styles.quoteText, item.reply.excerpt === null && styles.deletedText]} numberOfLines={2}>
              {item.reply.excerpt ?? "Message deleted"}
            </Text>
          </View>
        )}
        {item.attachment && <AttachmentCard attachment={item.attachment} />}
        {item.deleted ? (
          <Text style={styles.deletedText}>Message deleted</Text>
        ) : (
          <Text style={styles.body}>{item.body}</Text>
        )}
        <Text style={styles.time}>{sending ? "Sending…" : failed ? "" : timeLabel(item.createdAt)}</Text>
        {failed && (
          <Text style={styles.failedText}>
            Not sent. Tap to try again{item.error ? `\n${item.error}` : ""}
          </Text>
        )}
      </Pressable>
    </View>
  );
});

const useStyles = makeStyles((colors) => ({
  row: { paddingHorizontal: space.md, paddingVertical: 3, flexDirection: "row" },
  rowMine: { justifyContent: "flex-end" },
  rowTheirs: { justifyContent: "flex-start" },
  bubble: {
    maxWidth: "85%",
    borderRadius: radius.lg,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    gap: 2,
    borderWidth: 1,
  },
  bubbleMine: { backgroundColor: colors.primaryContainer, borderColor: colors.primaryContainer },
  bubbleTheirs: { backgroundColor: colors.surface, borderColor: colors.cardBorder },
  dim: { opacity: 0.6 },
  failed: { borderColor: colors.danger },
  name: { fontSize: 13, fontWeight: "700" },
  body: { fontSize: 16, color: colors.text },
  time: { fontSize: 13, color: colors.muted, alignSelf: "flex-end" },
  quote: {
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    backgroundColor: colors.divider,
    borderRadius: radius.sm,
    paddingHorizontal: space.sm,
    paddingVertical: 4,
    marginBottom: 2,
  },
  quoteName: { fontSize: 13, fontWeight: "700", color: colors.primary },
  quoteText: { fontSize: 13, color: colors.muted },
  deletedText: { fontSize: 14, fontStyle: "italic", color: colors.muted },
  failedText: { fontSize: 13, color: colors.danger },
}));
