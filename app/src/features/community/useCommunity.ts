import { useQueryClient } from "@tanstack/react-query";
import { useFocusEffect } from "expo-router";
import { randomUUID } from "expo-crypto";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppState } from "react-native";

import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";

import {
  deleteMessage,
  fetchChanges,
  fetchLatest,
  fetchOlder,
  postMessage,
  type CommunityMe,
} from "./api";
import { classifySendError } from "./sendError";
import { CommunitySocket, socketUrl, type SocketLike, type SocketState } from "./socket";
import {
  addPending,
  applyChanges,
  applyEvent,
  applyLatest,
  applyOlder,
  initialState,
  isLoaded,
  markFailed,
  removePending,
  retry as retryPending,
  visible,
  type ChatState,
} from "./store";

/** How often to ask "anything new?" while the socket is up (a safety net) and while it is not. */
const SYNC_LIVE_MS = 25_000;
const SYNC_OFFLINE_MS = 4_000;

/** True while the screen is in front of the person and the app is in the foreground. */
function useActive(): boolean {
  const [focused, setFocused] = useState(false);
  const [foreground, setForeground] = useState(AppState.currentState === "active");
  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      return () => setFocused(false);
    }, []),
  );
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (s) => setForeground(s === "active"));
    return () => subscription.remove();
  }, []);
  return focused && foreground;
}

/**
 * The community chat: keeps the conversation up to date while the screen is in front.
 *
 * Messages arrive three ways, all merged by id so none can show twice: pushed over the socket
 * (fast), asked for by the timed "anything new?" request (the safety net), and as the answer to
 * our own send. Only the request moves the cursor (see store.ts).
 */
export function useCommunity(me: CommunityMe | undefined) {
  const queryClient = useQueryClient();
  const active = useActive() && me !== undefined;

  // The state is also kept in a ref, so the timers and callbacks below always see the latest one
  // (and two changes in a row build on each other) without being recreated on every change.
  const [state, setState] = useState<ChatState>(initialState);
  const stateRef = useRef<ChatState>(initialState);
  const update = useCallback((change: (state: ChatState) => ChatState) => {
    const next = change(stateRef.current);
    if (next !== stateRef.current) {
      stateRef.current = next;
      setState(next);
    }
  }, []);

  const [socketState, setSocketState] = useState<SocketState>("offline");
  const socketStateRef = useRef<SocketState>("offline");
  const [online, setOnline] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const meRef = useRef(me);
  useEffect(() => {
    meRef.current = me;
  }, [me]);

  // --- Catching up -------------------------------------------------------------------------

  const syncing = useRef(false);
  const syncAgain = useRef(false);

  /** One "anything new?" at a time; asking while one is running runs it once more afterwards. */
  const sync = useCallback(async () => {
    if (syncing.current) {
      syncAgain.current = true;
      return;
    }
    syncing.current = true;
    try {
      do {
        syncAgain.current = false;
        const cursor = stateRef.current.cursor;
        if (cursor === null) {
          const page = await fetchLatest();
          update((s) => applyLatest(s, page));
        } else {
          const result = await fetchChanges(cursor);
          if (result.has_more) {
            // Too far behind to catch up message by message: start again from the latest.
            const page = await fetchLatest();
            update((s) => applyLatest(s, page));
          } else {
            update((s) => applyChanges(s, result));
          }
        }
        setLoadError(null);
      } while (syncAgain.current);
    } catch (error) {
      // A failed catch-up is only worth showing while there is nothing on screen; otherwise the
      // "no connection" line says enough and the next try follows.
      if (!isLoaded(stateRef.current)) setLoadError(error);
    } finally {
      syncing.current = false;
    }
  }, [update]);

  // --- The socket and the timer, only while the screen is in front -----------------------------

  useEffect(() => {
    if (!active) return;
    const socket = new CommunitySocket({
      url: socketUrl(env.apiUrl),
      getToken: async () => (await supabase.auth.getSession()).data.session?.access_token ?? null,
      createSocket: (url) => new WebSocket(url) as unknown as SocketLike,
      onState: (state) => {
        socketStateRef.current = state;
        setSocketState(state);
        if (state !== "live") setOnline(null);
      },
      onOnline: setOnline,
      onMessage: (message) => update((s) => applyEvent(s, message)),
      onReady: () => void sync(),
    });
    socket.start();

    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = () => {
      void sync();
      timer = setTimeout(tick, socketStateRef.current === "live" ? SYNC_LIVE_MS : SYNC_OFFLINE_MS);
    };
    tick();

    return () => {
      socket.stop();
      if (timer) clearTimeout(timer);
    };
  }, [active, sync, update]);

  // --- Older messages ------------------------------------------------------------------------

  const loadOlder = useCallback(async () => {
    const { oldestSeq, hasOlder } = stateRef.current;
    if (loadingOlder || !hasOlder || oldestSeq === null) return;
    setLoadingOlder(true);
    try {
      const page = await fetchOlder(oldestSeq);
      update((s) => applyOlder(s, page));
    } catch {
      // The list's footer offers it again the next time the person scrolls up.
    } finally {
      setLoadingOlder(false);
    }
  }, [loadingOlder, update]);

  // --- Sending and deleting --------------------------------------------------------------------

  /** Posts a message already shown as pending. Safe to repeat: the id is the same every time. */
  const deliver = useCallback(
    async (id: string, body: string, replyToId: string | null) => {
      try {
        const message = await postMessage({ id, body, replyToId });
        update((s) => removePending(applyEvent(s, message), id));
      } catch (error) {
        const failure = classifySendError(error);
        update((s) => markFailed(s, id, failure.message));
        // The server doesn't know the name (changed on another phone, or never saved): ask again.
        if (failure.needsName) void queryClient.invalidateQueries({ queryKey: ["community", "me"] });
      }
    },
    [queryClient, update],
  );

  /** Shows the message at once and posts it. Returns false when there is nothing to send yet. */
  const send = useCallback(
    (text: string, replyToId: string | null): boolean => {
      const body = text.trim();
      const current = meRef.current;
      if (!body || !current?.display_name || !isLoaded(stateRef.current)) return false;
      const id = randomUUID();
      update((s) =>
        addPending(s, {
          id,
          body,
          author: { id: current.user_id, name: current.display_name as string },
          replyToId,
          now: Date.now(),
        }),
      );
      void deliver(id, body, replyToId);
      return true;
    },
    [deliver, update],
  );

  /** Tap on "Not sent": send the same message again, with the same id. */
  const retry = useCallback(
    (id: string) => {
      const p = stateRef.current.pending.find((m) => m.id === id);
      if (!p || p.status !== "failed") return;
      update((s) => retryPending(s, id));
      void deliver(id, p.body, p.replyToId);
    },
    [deliver, update],
  );

  /** Gives up on a message that could not be sent. */
  const discard = useCallback((id: string) => update((s) => removePending(s, id)), [update]);

  /** Deletes a message on the server. Throws the server's message when it refuses. */
  const remove = useCallback(
    async (id: string) => {
      const message = await deleteMessage(id);
      update((s) => applyEvent(s, message));
    },
    [update],
  );

  const items = useMemo(() => visible(state), [state]);

  return {
    items,
    loaded: isLoaded(state),
    loadError,
    reload: sync,
    hasOlder: state.hasOlder,
    loadingOlder,
    loadOlder,
    socketState,
    online,
    send,
    retry,
    discard,
    remove,
  };
}
