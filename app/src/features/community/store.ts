// The community chat as the phone sees it: pure functions on a plain state object, no React Native
// imports, so `npm test` can run them. The screen keeps the state in a reducer.
//
// Two rules make the chat reliable:
//
// 1. `cursor` (the `rev` to ask "what changed since?" with) moves ONLY on answers from
//    GET /community/changes and on a fresh first page. A message pushed over the socket never moves
//    it. So the timed request is a real safety net, whatever the socket delivered or dropped: it
//    asks for everything after the cursor and the store merges it by id.
// 2. A message is merged by id and the copy with the higher `rev` wins, so the same message
//    arriving by socket, by sync and as the answer to the send changes nothing the second time.
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type CommunityMessage = Schemas["CommunityMessageOut"];
export type CommunityPage = Schemas["CommunityPageOut"];
export type CommunityChanges = Schemas["CommunityChangesOut"];

/** The message a reply answers, shortened. `excerpt` is null when that message was deleted. */
export type ReplyRef = { id: string; authorName: string; excerpt: string | null };

/** The same length the server uses for `reply_to.excerpt`. */
export const EXCERPT_CHARS = 140;

/** A message the person sent that the server has not confirmed yet. */
export type Pending = {
  id: string;
  body: string;
  author: { id: string; name: string };
  /** What the reply quotes, if we hold the message it answers. */
  reply: ReplyRef | null;
  /** The message it answers, kept so a retry sends the same thing. */
  replyToId: string | null;
  status: "sending" | "failed";
  /** Why it failed, for the "Not sent" line. */
  error: string | null;
  /** When it was written (ms), to keep unsent messages in the order they were written. */
  createdAt: number;
};

export type ChatState = {
  /** Confirmed messages by id. Deleted ones stay (with `deleted: true`). */
  messages: Readonly<Record<string, CommunityMessage>>;
  pending: readonly Pending[];
  /** The lowest `seq` loaded, for "load older" (`before=oldestSeq`). Null while nothing is loaded. */
  oldestSeq: number | null;
  hasOlder: boolean;
  /** The `rev` to ask GET /community/changes after. Null until the first page has been applied. */
  cursor: number | null;
};

export const initialState: ChatState = {
  messages: {},
  pending: [],
  oldestSeq: null,
  hasOlder: false,
  cursor: null,
};

/** Whether the first page has arrived. Before that, pushed messages are ignored: the page and the
 * changes after its `rev` bring them. */
export function isLoaded(state: ChatState): boolean {
  return state.cursor !== null;
}

/** What the list shows: one row per message, confirmed or not. */
export type ChatItem = {
  /** Stable across sending and confirming, so the row doesn't flicker when the server answers. */
  id: string;
  status: "sent" | "sending" | "failed";
  authorId: string;
  authorName: string;
  body: string | null;
  deleted: boolean;
  reply: ReplyRef | null;
  /** What the question is about (Ask the Community). Null for a plain message or a deleted one. */
  attachment: CommunityMessage["attachment"];
  /** ISO time for confirmed messages; unsent ones carry the time they were written. */
  createdAt: string;
  error: string | null;
};

/** Merges messages into the confirmed set. Pending sends that now exist for real are dropped. */
function merge(state: ChatState, incoming: readonly CommunityMessage[]): ChatState {
  if (incoming.length === 0) return state;
  let messages: Record<string, CommunityMessage> | null = null;
  // An empty room has no oldest message yet: the first ones to arrive set it.
  const oldestSeq = state.oldestSeq ?? Math.min(...incoming.map((m) => m.seq));
  for (const m of incoming) {
    const current = (messages ?? state.messages)[m.id];
    if (current) {
      if (current.rev >= m.rev) continue; // the copy we have is the same or newer
    } else if (m.seq < oldestSeq) {
      continue; // a change far up the history that isn't loaded: nothing to update
    }
    messages ??= { ...state.messages };
    messages[m.id] = m;
  }
  if (messages === null) return state;
  const pending = state.pending.filter((p) => !(p.id in messages));
  return { ...state, messages, pending, oldestSeq };
}

/**
 * The latest page (first load, or starting again after the phone fell too far behind): replaces
 * the confirmed messages and sets the cursor. Unsent messages are kept.
 */
export function applyLatest(state: ChatState, page: CommunityPage): ChatState {
  const messages: Record<string, CommunityMessage> = {};
  for (const m of page.items) messages[m.id] = m;
  return {
    messages,
    pending: state.pending.filter((p) => !(p.id in messages)),
    oldestSeq: page.items.length > 0 ? Math.min(...page.items.map((m) => m.seq)) : null,
    hasOlder: page.has_more,
    cursor: page.rev,
  };
}

/** An older page (`before=oldestSeq`). Does not touch the cursor. */
export function applyOlder(state: ChatState, page: CommunityPage): ChatState {
  const messages: Record<string, CommunityMessage> = { ...state.messages };
  for (const m of page.items) {
    const current = messages[m.id];
    if (!current || current.rev < m.rev) messages[m.id] = m;
  }
  const lowest = page.items.length > 0 ? Math.min(...page.items.map((m) => m.seq)) : null;
  return {
    ...state,
    messages,
    oldestSeq: lowest === null ? state.oldestSeq : Math.min(lowest, state.oldestSeq ?? lowest),
    hasOlder: page.has_more,
  };
}

/** The answer to GET /community/changes: merge, then move the cursor. */
export function applyChanges(state: ChatState, result: CommunityChanges): ChatState {
  if (!isLoaded(state)) return state;
  const merged = merge(state, result.items);
  return { ...merged, cursor: Math.max(state.cursor ?? 0, result.rev) };
}

/** A message pushed over the socket, or the server's answer to our own send. NEVER moves the cursor. */
export function applyEvent(state: ChatState, message: CommunityMessage): ChatState {
  if (!isLoaded(state)) return state;
  return merge(state, [message]);
}

export function excerpt(body: string): string {
  const flat = body.split(/\s+/).filter(Boolean).join(" ");
  return flat.length <= EXCERPT_CHARS ? flat : flat.slice(0, EXCERPT_CHARS - 1).trimEnd() + "…";
}

/** What a reply to this message would quote, from the copy we hold. Null if we don't have it. */
export function replyRefTo(state: ChatState, id: string): ReplyRef | null {
  const m = state.messages[id];
  if (!m) return null;
  return {
    id: m.id,
    authorName: m.author_name,
    excerpt: m.deleted || m.body === null ? null : excerpt(m.body),
  };
}

type NewPending = {
  id: string;
  body: string;
  author: { id: string; name: string };
  replyToId?: string | null;
  now: number;
};

/** Shows a message the moment it is sent. No-op when that id is already there. */
export function addPending(state: ChatState, input: NewPending): ChatState {
  if (input.id in state.messages || state.pending.some((p) => p.id === input.id)) return state;
  const pending: Pending = {
    id: input.id,
    body: input.body,
    author: input.author,
    reply: input.replyToId ? replyRefTo(state, input.replyToId) : null,
    replyToId: input.replyToId ?? null,
    status: "sending",
    error: null,
    createdAt: input.now,
  };
  return { ...state, pending: [...state.pending, pending] };
}

function updatePending(state: ChatState, id: string, change: Partial<Pending>): ChatState {
  if (!state.pending.some((p) => p.id === id)) return state;
  return { ...state, pending: state.pending.map((p) => (p.id === id ? { ...p, ...change } : p)) };
}

/** The send did not go through. It stays, with the reason, for "Not sent. Tap to try again". */
export function markFailed(state: ChatState, id: string, reason: string): ChatState {
  return updatePending(state, id, { status: "failed", error: reason });
}

/** Tapped "try again": back to sending. The id stays the same, so the server can't post it twice. */
export function retry(state: ChatState, id: string): ChatState {
  return updatePending(state, id, { status: "sending", error: null });
}

/** Gives up on a send (the person removed it, or the server refused it for good). */
export function removePending(state: ChatState, id: string): ChatState {
  if (!state.pending.some((p) => p.id === id)) return state;
  return { ...state, pending: state.pending.filter((p) => p.id !== id) };
}

/**
 * The conversation, oldest first: confirmed messages by `seq`, then unsent ones in the order they
 * were written. A reply quotes the local copy of its target when there is one (so a message
 * deleted since shows as deleted), else what the server sent.
 */
export function visible(state: ChatState): ChatItem[] {
  const confirmed = Object.values(state.messages).sort((a, b) => a.seq - b.seq);
  const items: ChatItem[] = confirmed.map((m) => ({
    id: m.id,
    status: "sent",
    authorId: m.author_id,
    authorName: m.author_name,
    body: m.deleted ? null : m.body,
    attachment: m.deleted ? null : (m.attachment ?? null),
    deleted: m.deleted,
    reply: m.reply_to
      ? (replyRefTo(state, m.reply_to.id) ?? {
          id: m.reply_to.id,
          authorName: m.reply_to.author_name,
          excerpt: m.reply_to.excerpt,
        })
      : null,
    createdAt: m.created_at,
    error: null,
  }));
  const unsent = [...state.pending].sort((a, b) => a.createdAt - b.createdAt);
  for (const p of unsent) {
    items.push({
      id: p.id,
      status: p.status === "failed" ? "failed" : "sending",
      authorId: p.author.id,
      authorName: p.author.name,
      body: p.body,
      attachment: null,
      deleted: false,
      reply: p.reply ? (replyRefTo(state, p.reply.id) ?? p.reply) : null,
      createdAt: new Date(p.createdAt).toISOString(),
      error: p.error,
    });
  }
  return items;
}
