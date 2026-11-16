import { randomUUID } from "expo-crypto";
import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Modal, Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button, ErrorText, Field, TextLink } from "@/ui/components";
import { Check, ICON, MessagesSquare } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, space, TOUCH, useTheme } from "@/ui/theme";

import { postMessage, useCommunityMe } from "./api";
import { ASK_PROMPTS, type Attachment } from "./ask";
import { AttachmentCard } from "./AttachmentCard";
import { NameForm } from "./NameForm";
import { classifySendError } from "./sendError";

/**
 * "Ask the Community" next to a word, an exercise, a chapter, a rule or a course resource. Opens
 * a sheet over the screen (so a practice round or a scanned exercise is not lost), with the item
 * as a card, quick prompts and a box for the question. It posts to the group chat like any other
 * message, and people answer with the chat's normal reply.
 *
 * `attachment` is built when the sheet opens, so it carries the learner's latest answer.
 */
export function AskCommunityButton({
  attachment,
  iconOnly = false,
  about,
}: {
  attachment: () => Attachment;
  /** Just the icon (48dp), for a crowded row. `about` then names the item for screen readers. */
  iconOnly?: boolean;
  about?: string;
}) {
  const styles = useStyles();
  const colors = useTheme();
  const [open, setOpen] = useState<Attachment | null>(null);
  return (
    <>
      {iconOnly ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={about ? `Ask the Community about ${about}` : "Ask the Community"}
          onPress={() => setOpen(attachment())}
          android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
          style={styles.iconButton}
        >
          <MessagesSquare size={ICON.inline} color={colors.primary} />
        </Pressable>
      ) : (
        <TextLink
          label="Ask the Community"
          icon={MessagesSquare}
          hint="Share this in the group chat with your question"
          onPress={() => setOpen(attachment())}
        />
      )}
      {open && <AskSheet attachment={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function AskSheet({ attachment, onClose }: { attachment: Attachment; onClose: () => void }) {
  const styles = useStyles();
  const colors = useTheme();
  const insets = useSafeAreaInsets();
  const me = useCommunityMe();
  const [text, setText] = useState("");
  // Made once, so pressing Send again after a dropped connection can never post twice.
  const [id] = useState(() => randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const question = text.trim();

  async function send() {
    setBusy(true);
    setError(null);
    try {
      await postMessage({ id, body: question, replyToId: null, attachment });
      setSent(true);
    } catch (e) {
      const failure = classifySendError(e);
      setError(failure.message);
      if (failure.needsName) void me.refetch();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent navigationBarTranslucent>
      <Pressable style={styles.scrim} onPress={onClose} accessibilityLabel="Close" />
      <KeyboardAvoidingView behavior="padding" style={styles.holder} pointerEvents="box-none">
        <View style={[styles.sheet, { paddingBottom: insets.bottom + space.lg }]} accessibilityViewIsModal>
          <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
            <Text style={styles.title} accessibilityRole="header">
              Ask the Community
            </Text>
            <AttachmentCard attachment={attachment} />

            {sent ? (
              <>
                <View style={styles.sentRow} accessibilityLiveRegion="polite">
                  <Check size={ICON.bar} strokeWidth={3} color={colors.success} />
                  <Text style={styles.sentText}>Sent to the group chat. Answers show up there.</Text>
                </View>
                <Button
                  label="Open the chat"
                  onPress={() => {
                    onClose();
                    router.navigate("/community");
                  }}
                />
                <Button label="Done" variant="secondary" onPress={onClose} />
              </>
            ) : me.data && me.data.display_name === null ? (
              // Every signed-in person has a username (the app asks on first sign-in); this only shows if that check could not run, for example offline.
              <NameForm onDone={() => void me.refetch()} />
            ) : (
              <>
                <View style={styles.prompts}>
                  {ASK_PROMPTS.map((p) => (
                    <Pressable
                      key={p}
                      accessibilityRole="button"
                      accessibilityHint="Writes this into your question"
                      onPress={() => setText(p)}
                      android_ripple={{ color: colors.divider }}
                      style={[styles.prompt, text === p && styles.promptOn]}
                    >
                      <Text style={[styles.promptText, text === p && styles.promptTextOn]}>{p}</Text>
                    </Pressable>
                  ))}
                </View>
                <Field
                  label="Your question"
                  value={text}
                  onChangeText={setText}
                  multiline
                  maxLength={me.data?.max_message_chars ?? 2000}
                  placeholder="What would you like to know?"
                  style={styles.box}
                  textAlignVertical="top"
                />
                <Text style={styles.note}>
                  Everyone in the chat sees this, with your chat name. Only the text above is shared,
                  never a link or your email.
                </Text>
                {error && <ErrorText error={error} />}
                <Button label="Send to the Community" busy={busy} disabled={!question} onPress={() => void send()} />
                <Button label="Cancel" variant="secondary" onPress={onClose} />
              </>
            )}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const useStyles = makeStyles((colors) => ({
  iconButton: { width: TOUCH, height: TOUCH, alignItems: "center", justifyContent: "center" },
  scrim: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, backgroundColor: colors.scrim },
  holder: { flex: 1, justifyContent: "flex-end" },
  sheet: {
    maxHeight: "88%",
    backgroundColor: colors.sheet,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    borderTopWidth: 1,
    borderColor: colors.cardBorder,
    boxShadow: `0 -8px 32px ${colors.shadow}`,
  },
  content: { padding: space.lg + space.xs, gap: space.md },
  title: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  prompts: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  prompt: {
    minHeight: TOUCH,
    justifyContent: "center",
    paddingHorizontal: space.lg,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  promptOn: { backgroundColor: colors.primaryContainer, borderColor: colors.primaryContainer },
  promptText: { fontSize: 15, lineHeight: 22, fontWeight: "600" },
  promptTextOn: { color: colors.onPrimaryContainer, fontWeight: "700" },
  box: { minHeight: 96 },
  note: { fontSize: 14, lineHeight: 20, color: colors.muted },
  sentRow: { flexDirection: "row", alignItems: "center", gap: space.sm },
  sentText: { flex: 1, fontSize: 16, lineHeight: 24, fontWeight: "700" },
}));
