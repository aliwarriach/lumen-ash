// The Today screen's plain rules: greeting, week strip, what "Continue" opens, the next badge.
// Pure functions, no React Native, so they are tested with node:test (tests/today.test.ts).
import type { components } from "../../api/schema";

type Dashboard = components["schemas"]["DashboardOut"];
type PlanItem = components["schemas"]["PlanItemOut"];

/** "Guten Morgen!" until 11, "Guten Tag!" until 18, then "Guten Abend!". */
export function greeting(hour: number): string {
  if (hour >= 5 && hour < 11) return "Guten Morgen!";
  if (hour >= 11 && hour < 18) return "Guten Tag!";
  return "Guten Abend!";
}

/** Done by the server's evidence, or ticked by the learner for things the app can't see. */
export function isDone(item: PlanItem, ticked: readonly string[]): boolean {
  return item.done === true || (item.done === null && ticked.includes(item.id));
}

/** What "Continue" opens: the first thing in the plan that isn't done yet. */
export function nextItem(items: readonly PlanItem[], ticked: readonly string[]): PlanItem | null {
  return items.find((i) => !isDone(i, ticked)) ?? null;
}

export type WeekDay = {
  /** Two letters: Mo, Tu, We, Th, Fr, Sa, Su. */
  label: string;
  /** The full name, for the screen reader. */
  name: string;
  done: boolean;
  today: boolean;
  future: boolean;
};

const DAYS = [
  ["Mo", "Monday"],
  ["Tu", "Tuesday"],
  ["We", "Wednesday"],
  ["Th", "Thursday"],
  ["Fr", "Friday"],
  ["Sa", "Saturday"],
  ["Su", "Sunday"],
] as const;

/** Monday is 0. Dates are the learner's local YYYY-MM-DD, read without a time zone. */
function weekday(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

/**
 * Monday to Sunday of the current week, from the days studied (`on_track.week`) and today.
 * `studied` can be missing: a plan saved on the phone, or sent by a server, from before the
 * field existed. The strip then shows no studied days instead of failing.
 */
export function weekStrip(studied: readonly string[] | undefined, today: string): WeekDay[] {
  const now = weekday(today);
  const done = new Set((studied ?? []).map(weekday));
  return DAYS.map(([label, name], i) => ({
    label,
    name,
    done: done.has(i),
    today: i === now,
    future: i > now,
  }));
}

export type Badge = {
  /** e.g. "7 days in a row". */
  title: string;
  /** Where the learner is now, e.g. "5/7". */
  progress: string;
  /** e.g. "2 more days to go", or what was done to earn it. */
  detail: string;
  /** Earned today: the streak reached this milestone with today's study. */
  isNew: boolean;
};

const STREAK = [3, 7, 14, 30, 60, 100, 200, 365];
const WORDS = [10, 25, 50, 100, 200, 350, 500, 750, 1000];
const CHAPTERS = [1, 3, 6, 9, 12, 16, 20, 24];

type Track = {
  value: number;
  steps: readonly number[];
  title: (n: number) => string;
  togo: (n: number) => string;
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * The badge row. A streak milestone reached today is a new badge; otherwise it shows the badge
 * the learner is closest to (by share of the way there), so there is always a next goal.
 * Null when every milestone is reached.
 */
export function nextBadge(data: Dashboard): Badge | null {
  const streak = data.on_track.streak;
  const studiedToday = data.on_track.last_studied === data.date;
  if (studiedToday && STREAK.includes(streak)) {
    return {
      title: `${streak} days in a row`,
      progress: `${streak}/${streak}`,
      detail: `You studied ${streak} days in a row.`,
      isNew: true,
    };
  }

  const tracks: Track[] = [
    {
      value: streak,
      steps: STREAK,
      title: (n) => `${n} days in a row`,
      togo: (n) => `${plural(n, "more day", "more days")} to go`,
    },
    {
      value: data.vocabulary.mastered,
      steps: WORDS,
      title: (n) => `${n} words known`,
      togo: (n) => `${plural(n, "more word", "more words")} to know well`,
    },
    {
      value: data.chapters.completed,
      steps: CHAPTERS.filter((n) => n <= Math.max(data.chapters.total, CHAPTERS[0])),
      title: (n) => (n === 1 ? "First chapter done" : `${n} chapters done`),
      togo: (n) => `${plural(n, "more chapter", "more chapters")} to finish`,
    },
  ];

  let best: { share: number; badge: Badge } | null = null;
  for (const t of tracks) {
    const target = t.steps.find((n) => n > t.value);
    if (target === undefined) continue;
    const share = t.value / target;
    if (best === null || share > best.share) {
      best = {
        share,
        badge: {
          title: t.title(target),
          progress: `${t.value}/${target}`,
          detail: t.togo(target - t.value),
          isNew: false,
        },
      };
    }
  }
  return best?.badge ?? null;
}
