import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, Share, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";

import { useCommunityMe } from "@/features/community/api";
import { Composer } from "@/features/community/Composer";
import { MessageBubble } from "@/features/community/MessageBubble";
import { NameForm } from "@/features/community/NameForm";
import { toRows, type ChatRow } from "@/features/community/rows";
import type { ChatItem } from "@/features/community/store";
import { useCommunity } from "@/features/community/useCommunity";
import { Button, Centered, ErrorText, IconLabel, Loading } from "@/ui/components";
import { AvoidKeyboard } from "@/ui/FormScroll";
import { ArrowDown, ICON } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

/** Scrolled further than this from the newest message counts as "reading older messages". */
const AWAY_PX = 120;

export default function Community() {
  const colors = useTheme();
  const styles = useStyles();
  const meQuery = useCommunityMe();
  const me = meQuery.data;
  const chat = useCommunity(me);

  const [replyTo, setReplyTo] = useState<ChatItem | null>(null);
  const [away, setAway] = useState(false);
  // The newest message the reader had seen when they scrolled up (or pressed the button).
  const [seenId, setSeenId] = useState<string | null>(null);
  const awayRef = useRef(false);
  const listRef = useRef<FlatList<ChatRow>>(null);

  const rows = useMemo(() => toRows(chat.items), [chat.items]);
  const myId = me?.user_id;

  // Someone else's message arrived while the reader is further up: offer a way back down. The list
  // itself keeps their place (maintainVisibleContentPosition), so nothing moves under them.
  const newest = chat.items.length > 0 ? chat.items[chat.items.length - 1] : null;
  const newestIdRef = useRef<string | null>(null);
  useEffect(() => {
    newestIdRef.current = newest?.id ?? null;
  }, [newest]);
  const unseen = away && newest !== null && newest.authorId !== myId && newest.id !== seenId;

  const scrollToNewest = useCallback(() => {
    listRef.current?.scrollToOffset({ offset: 0, animated: true });
    setSeenId(newestIdRef.current);
  }, []);

  const onScroll = useCallback((e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const isAway = e.nativeEvent.contentOffset.y > AWAY_PX;
    if (isAway === awayRef.current) return;
    awayRef.current = isAway;
    setAway(isAway);
    setSeenId(newestIdRef.current);
  }, []);

  const canDelete = useCallback(
    (item: ChatItem) => !!me && (item.authorId === me.user_id || me.moderator),
    [me],
  );

  const confirmDelete = useCallback(
    (item: ChatItem) => {
      Alert.alert("Delete this message?", "Everyone will see that it was deleted.", [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            chat.remove(item.id).catch((error: unknown) =>
              Alert.alert("Could not delete", error instanceof Error ? error.message : "Try again."),
            );
          },
        },
      ]);
    },
    [chat],
  );

  const onLongPress = useCallback(
    (item: ChatItem) => {
      // Android shows at most three buttons; tapping outside closes the menu.
      const buttons = [
        { text: "Reply", onPress: () => setReplyTo(item) },
        { text: "Share or copy", onPress: () => void Share.share({ message: item.body ?? "" }) },
        ...(canDelete(item)
          ? [{ text: "Delete", style: "destructive" as const, onPress: () => confirmDelete(item) }]
          : []),
      ];
      Alert.alert(item.authorName, undefined, buttons, { cancelable: true });
    },
    [canDelete, confirmDelete],
  );

  const onPressFailed = useCallback(
    (item: ChatItem) => {
      Alert.alert("Message not sent", item.error ?? undefined, [
        { text: "Try again", onPress: () => chat.retry(item.id) },
        { text: "Remove", style: "destructive", onPress: () => chat.discard(item.id) },
      ], { cancelable: true });
    },
    [chat],
  );

  const renderItem = useCallback(
    ({ item: row }: { item: ChatRow }) =>
      row.kind === "day" ? (
        <View style={styles.dayWrap}>
          <Text style={styles.day}>{row.label}</Text>
        </View>
      ) : (
        <MessageBubble
          item={row.item}
          mine={row.item.authorId === myId}
          onLongPress={onLongPress}
          onPressFailed={onPressFailed}
        />
      ),
    [myId, onLongPress, onPressFailed, styles],
  );

  if (!me) {
    return (
      <Centered>
        {meQuery.isError ? (
          <View style={styles.gap}>
            <ErrorText error={meQuery.error} />
            <Button label="Try again" variant="secondary" onPress={() => void meQuery.refetch()} />
          </View>
        ) : (
          <Loading label="Opening the chat…" />
        )}
      </Centered>
    );
  }

  if (!chat.loaded) {
    return (
      <Centered>
        {chat.loadError ? (
          <View style={styles.gap}>
            <ErrorText error={chat.loadError} />
            <Button label="Try again" variant="secondary" onPress={() => void chat.reload()} />
          </View>
        ) : (
          <Loading label="Loading the chat…" />
        )}
      </Centered>
    );
  }

  const needsName = me.display_name === null;

  return (
    <AvoidKeyboard>
      <StatusLine state={chat.socketState} online={chat.online} />
      <View style={styles.listWrap}>
        <FlatList
          ref={listRef}
          data={rows}
          renderItem={renderItem}
          keyExtractor={(row) => row.key}
          inverted
          keyboardShouldPersistTaps="handled"
          maintainVisibleContentPosition={{ minIndexForVisible: 0, autoscrollToTopThreshold: AWAY_PX }}
          onScroll={onScroll}
          scrollEventThrottle={100}
          onEndReached={() => void chat.loadOlder()}
          onEndReachedThreshold={0.5}
          contentContainerStyle={styles.listContent}
          ListEmptyComponent={
            <View style={styles.flip}>
              <Text style={styles.empty}>No messages yet. Ask the first question!</Text>
            </View>
          }
          ListFooterComponent={
            chat.loadingOlder ? (
              <ActivityIndicator style={styles.footer} color={colors.primary} />
            ) : rows.length > 0 && !chat.hasOlder ? (
              <Text style={[styles.empty, styles.footer]}>This is the start of the conversation.</Text>
            ) : (
              <View />
            )
          }
        />
        {unseen && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="New messages. Go to the newest."
            onPress={scrollToNewest}
            android_ripple={{ color: colors.onPrimary + "33" }}
            style={styles.newMessages}
          >
            <IconLabel trailing icon={ArrowDown} size={ICON.small} color={colors.onPrimary} style={styles.newMessagesText}>
              New messages
            </IconLabel>
          </Pressable>
        )}
      </View>
      {needsName ? (
        <NameForm />
      ) : (
        <Composer
          maxChars={me.max_message_chars}
          replyingTo={replyTo}
          onCancelReply={() => setReplyTo(null)}
          onSend={(text) => {
            const sent = chat.send(text, replyTo?.id ?? null);
            if (sent) {
              setReplyTo(null);
              scrollToNewest();
            }
            return sent;
          }}
          bottomInset={0}
        />
      )}
    </AvoidKeyboard>
  );
}

function StatusLine({ state, online }: { state: "connecting" | "live" | "offline"; online: number | null }) {
  const styles = useStyles();
  const text =
    state === "live"
      ? online === null
        ? "Connected"
        : `${online} here now`
      : state === "connecting"
        ? "Connecting…"
        : "No connection. Messages will arrive when you are back online.";
  return (
    <View style={[styles.status, state === "offline" && styles.statusOffline]} accessibilityLiveRegion="polite">
      <Text style={[styles.statusText, state === "offline" && styles.statusTextOffline]}>{text}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  gap: { gap: space.md, alignItems: "center" },
  listWrap: { flex: 1 },
  listContent: { paddingVertical: space.sm },
  flip: { transform: [{ scaleY: -1 }], padding: space.xl },
  empty: { color: colors.muted, textAlign: "center", fontSize: 13 },
  footer: { padding: space.lg },
  dayWrap: { alignItems: "center", paddingVertical: space.sm },
  day: {
    fontSize: 13,
    color: colors.muted,
    backgroundColor: colors.divider,
    borderRadius: radius.lg,
    paddingHorizontal: space.md,
    paddingVertical: 2,
    overflow: "hidden",
  },
  status: { paddingHorizontal: space.md, paddingVertical: 4, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.divider },
  statusOffline: { backgroundColor: colors.amber.bg },
  statusText: { fontSize: 13, color: colors.muted, textAlign: "center" },
  statusTextOffline: { color: colors.amber.fg },
  newMessages: {
    position: "absolute",
    bottom: space.md,
    alignSelf: "center",
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    paddingHorizontal: space.lg,
    minHeight: TOUCH,
    justifyContent: "center",
    overflow: "hidden",
  },
  newMessagesText: { color: colors.onPrimary, fontWeight: "700" },
}));
