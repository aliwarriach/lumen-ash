// Reminders for class tasks, scheduled on the phone. No server and no background worker: Android
// fires each one at its time, even when the app is closed.
//
// The server keeps each task's `remind_at`; the phone keeps a small map of which notification
// belongs to which task. `syncTaskReminders` makes the phone match the server: it is safe to call
// any number of times, and it also sets reminders up again after a reinstall or on a new phone.
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Notifications from "expo-notifications";
import { AndroidImportance } from "expo-notifications";
import { useEffect } from "react";
import { Platform } from "react-native";

import { useClassTasks, formatDate, type ClassTask } from "@/features/capture/api";

const KEY = "task-reminders:v1";
const CHANNEL = "class-tasks";
const EVENING_BEFORE_HOUR = 18;
const MORNING_OF_HOUR = 8;
const MIN_LEAD_MS = 60_000; // a reminder less than a minute away is no reminder

export type ReminderChoice = "evening_before" | "morning_of" | "none";

export const CHOICE_LABELS: Record<ReminderChoice, string> = {
  evening_before: "Evening before, 18:00",
  morning_of: "Morning of, 08:00",
  none: "No reminder",
};

/** The local date and time for a choice, or null if there is no date or that time has passed. */
export function reminderTime(
  choice: ReminderChoice,
  dueIso: string | null,
  now: Date = new Date(),
): Date | null {
  if (choice === "none" || !dueIso) return null;
  const [y, m, d] = dueIso.split("-").map(Number);
  if (!y || !m || !d) return null;
  const at =
    choice === "evening_before"
      ? new Date(y, m - 1, d - 1, EVENING_BEFORE_HOUR, 0)
      : new Date(y, m - 1, d, MORNING_OF_HOUR, 0);
  return at.getTime() - now.getTime() >= MIN_LEAD_MS ? at : null;
}

/** The evening before if that is still ahead, else the morning of, else none. */
export function defaultChoice(dueIso: string | null, now: Date = new Date()): ReminderChoice {
  if (reminderTime("evening_before", dueIso, now)) return "evening_before";
  if (reminderTime("morning_of", dueIso, now)) return "morning_of";
  return "none";
}

/** "Thu 12 Nov, 18:00" */
export function describeReminder(at: Date): string {
  const iso = `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, "0")}-${String(at.getDate()).padStart(2, "0")}`;
  const time = `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
  return `${formatDate(iso)}, ${time}`;
}

type Stored = Record<string, { notificationId: string; at: string }>;

async function load(): Promise<Stored> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Stored) : {};
  } catch {
    return {};
  }
}

async function save(stored: Stored): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(stored)).catch(() => undefined);
}

async function cancel(notificationId: string): Promise<void> {
  await Notifications.cancelScheduledNotificationAsync(notificationId).catch(() => undefined);
}

async function ensureChannel(): Promise<void> {
  if (Platform.OS === "android") {
    // The permission prompt on Android 13+ only appears once a channel exists.
    await Notifications.setNotificationChannelAsync(CHANNEL, {
      name: "Class task reminders",
      importance: AndroidImportance.DEFAULT,
    });
  }
}

/** Asks for notification permission if it hasn't been decided. True when reminders can be shown. */
export async function ensureNotificationPermission(): Promise<boolean> {
  await ensureChannel();
  let { status } = await Notifications.getPermissionsAsync();
  if (status !== "granted") ({ status } = await Notifications.requestPermissionsAsync());
  return status === "granted";
}

// Syncs run one after another: two at once could schedule the same reminder twice.
let queue: Promise<void> = Promise.resolve();

/** Makes the phone's scheduled reminders match `tasks`: the open ones with a reminder ahead. */
export function syncTaskReminders(tasks: ClassTask[], now: Date = new Date()): Promise<void> {
  queue = queue.then(() => sync(tasks, now)).catch(() => undefined);
  return queue;
}

async function sync(tasks: ClassTask[], now: Date): Promise<void> {
  const stored = await load();
  const wanted = new Map<string, ClassTask>();
  for (const t of tasks) {
    if (!t.done && t.remind_at && new Date(t.remind_at).getTime() - now.getTime() >= MIN_LEAD_MS) {
      wanted.set(t.id, t);
    }
  }

  const next: Stored = {};
  for (const [taskId, entry] of Object.entries(stored)) {
    const task = wanted.get(taskId);
    if (task && task.remind_at === entry.at) next[taskId] = entry; // already right
    else await cancel(entry.notificationId); // finished, deleted, moved or in the past
  }

  const { status } = await Notifications.getPermissionsAsync();
  if (status === "granted") {
    await ensureChannel();
    for (const [taskId, task] of wanted) {
      if (next[taskId] || !task.remind_at) continue;
      try {
        const notificationId = await Notifications.scheduleNotificationAsync({
          content: {
            title: "German class task",
            body: task.due_date ? `${task.title} · due ${formatDate(task.due_date)}` : task.title,
          },
          trigger: {
            type: Notifications.SchedulableTriggerInputTypes.DATE,
            date: new Date(task.remind_at),
            channelId: CHANNEL,
          },
        });
        next[taskId] = { notificationId, at: task.remind_at };
      } catch {
        // One failed reminder shouldn't stop the others; the next sync tries again.
      }
    }
  }
  await save(next);
}

/** On sign out: the reminders belong to the account, so they go with it. */
export function clearTaskReminders(): Promise<void> {
  queue = queue
    .then(async () => {
      const stored = await load();
      for (const entry of Object.values(stored)) await cancel(entry.notificationId);
      await AsyncStorage.removeItem(KEY).catch(() => undefined);
    })
    .catch(() => undefined);
  return queue;
}

/** Keeps the phone's reminders in step with the server. Mount once, while signed in. */
export function useTaskReminderSync(): void {
  const tasks = useClassTasks(false);
  useEffect(() => {
    // Only trust a successful answer: offline, the reminders already set stay as they are.
    if (tasks.isSuccess) void syncTaskReminders(tasks.data);
  }, [tasks.isSuccess, tasks.data]);
}
