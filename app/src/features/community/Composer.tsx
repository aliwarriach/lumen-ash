import { useState } from "react";
import { Pressable, View } from "react-native";

import { ICON, X } from "@/ui/icons";
import { Text, TextInput } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

import type { ChatItem } from "./store";

type Props = {
  maxChars: number;
  /** The message being answered, shown above the input with a way to cancel. */
  replyingTo: ChatItem | null;
  onCancelReply: () => void;
  /** Returns false when nothing was sent (the text stays). */
  onSend: (text: string) => boolean;
  /** Space under the input: the system navigation bar's height while the keyboard is closed. */
  bottomInset: number;
};

const LINE_HEIGHT = 22;
const MAX_LINES = 5;

/** The input at the bottom of the chat. Sending keeps the keyboard open for the next message. */
export function Composer({ maxChars, replyingTo, onCancelReply, onSend, bottomInset }: Props) {
  const styles = useStyles();
  const colors = useTheme();
  const [text, setText] = useState("");
  const empty = text.trim().length === 0;
  const nearLimit = text.length >= maxChars * 0.8;

  function send() {
    if (empty) return;
    if (onSend(text)) setText("");
  }

  return (
    <View style={[styles.wrap, { paddingBottom: space.sm + bottomInset }]}>
      {replyingTo && (
        <View style={styles.replying}>
          <View style={styles.replyingText}>
            <Text style={styles.replyingName} numberOfLines={1}>
              Replying to {replyingTo.authorName}
            </Text>
            <Text style={styles.replyingBody} numberOfLines={1}>
              {replyingTo.body}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Cancel reply"
            onPress={onCancelReply}
            android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
            style={styles.cancelReply}
          >
            <X size={ICON.inline} color={colors.muted} />
          </Pressable>
        </View>
      )}
      <View style={styles.inputRow}>
        <TextInput
          style={[styles.input, { maxHeight: LINE_HEIGHT * MAX_LINES + space.md * 2 }]}
          value={text}
          onChangeText={setText}
          placeholder="Write a message"
          placeholderTextColor={colors.muted}
          accessibilityLabel="Message"
          multiline
          maxLength={maxChars}
          textAlignVertical="top"
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Send"
          accessibilityState={{ disabled: empty }}
          disabled={empty}
          onPress={send}
          style={({ pressed }) => [styles.send, (empty || pressed) && styles.sendOff]}
        >
          <Text style={styles.sendText}>Send</Text>
        </Pressable>
      </View>
      {nearLimit && (
        <Text style={[styles.counter, text.length >= maxChars && styles.counterFull]}>
          {text.length} / {maxChars}
        </Text>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  wrap: {
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingHorizontal: space.md,
    paddingTop: space.sm,
    gap: space.xs,
  },
  replying: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    backgroundColor: colors.background,
    borderRadius: radius.sm,
    paddingHorizontal: space.sm,
    paddingVertical: 4,
  },
  replyingText: { flex: 1 },
  cancelReply: { width: TOUCH, height: TOUCH, alignItems: "center", justifyContent: "center", marginVertical: -4 },
  replyingName: { fontSize: 13, fontWeight: "700", color: colors.primary },
  replyingBody: { fontSize: 13, color: colors.muted },
  inputRow: { flexDirection: "row", alignItems: "flex-end", gap: space.sm },
  input: {
    flex: 1,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: space.md,
    paddingVertical: space.md,
    fontSize: 16,
    lineHeight: LINE_HEIGHT,
    color: colors.text,
  },
  send: {
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    paddingHorizontal: space.lg,
    justifyContent: "center",
    minHeight: 48,
  },
  sendOff: { opacity: 0.5 },
  sendText: { color: colors.onPrimary, fontSize: 16, fontWeight: "600" },
  counter: { alignSelf: "flex-end", fontSize: 13, color: colors.muted },
  counterFull: { color: colors.danger },
}));
