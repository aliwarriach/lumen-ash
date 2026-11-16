// What the chat list draws: messages with a day heading above the first message of each day.
// Pure (no React Native), so it is tested.
import type { ChatItem } from "./store";

export type ChatRow =
  | { kind: "message"; key: string; item: ChatItem }
  | { kind: "day"; key: string; label: string };

function dayStart(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** "Today", "Yesterday", or "Thu 12 Nov" (with the year when it is not this year). */
export function dayLabel(date: Date, now: Date, locale?: string): string {
  const diff = Math.round((dayStart(now) - dayStart(date)) / DAY_MS);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return date.toLocaleDateString(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
  });
}

/**
 * Rows for an inverted list: NEWEST FIRST. `items` is oldest first (as `visible()` returns it). A
 * day heading comes right after (that is, visually above) the oldest message of its day.
 */
export function toRows(items: readonly ChatItem[], now: Date = new Date(), locale?: string): ChatRow[] {
  const rows: ChatRow[] = [];
  let currentDay: number | null = null;
  for (const item of items) {
    const when = new Date(item.createdAt);
    const day = dayStart(when);
    if (day !== currentDay) {
      rows.push({ kind: "day", key: `day-${day}`, label: dayLabel(when, now, locale) });
      currentDay = day;
    }
    rows.push({ kind: "message", key: item.id, item });
  }
  return rows.reverse();
}

/**
 * The same person always gets the same colour, picked from the theme's name colours (distinct and
 * readable on the message bubbles; none is the error red or the app's own primary).
 */
export function authorColor(authorId: string, names: readonly string[]): string {
  let hash = 0;
  for (let i = 0; i < authorId.length; i++) hash = (hash * 31 + authorId.charCodeAt(i)) >>> 0;
  return names[hash % names.length];
}

/** "14:05" in the phone's own format. */
export function timeLabel(iso: string, locale?: string): string {
  return new Date(iso).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}
