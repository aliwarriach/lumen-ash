// A daily study reminder, scheduled on the phone. No server and no background worker: Android
// itself fires it every day at the chosen time, even when the app is closed.
//
// It repeats at a fixed time and says the same thing every day, because nothing can run in the
// background to check whether the learner has already studied. Android may deliver it a few
// minutes late ("best effort"), which is fine for a study nudge.
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Notifications from "expo-notifications";
import { AndroidImportance } from "expo-notifications";
import { useCallback, useEffect, useState } from "react";
import { Platform } from "react-native";

const KEY = "reminder:v1";
const CHANNEL = "daily-reminder";

export type Reminder = {
  enabled: boolean;
  hour: number;
  minute: number;
  /** The scheduled notification, so changing or removing the reminder cancels exactly this one. */
  notificationId: string | null;
};

export const DEFAULT_REMINDER: Reminder = { enabled: false, hour: 18, minute: 0, notificationId: null };

// Show the reminder even while the app is open.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export function formatTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

async function load(): Promise<Reminder> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? { ...DEFAULT_REMINDER, ...(JSON.parse(raw) as Partial<Reminder>) } : DEFAULT_REMINDER;
  } catch {
    return DEFAULT_REMINDER;
  }
}

async function save(reminder: Reminder): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(reminder));
}

async function cancel(notificationId: string | null): Promise<void> {
  if (notificationId) {
    await Notifications.cancelScheduledNotificationAsync(notificationId).catch(() => undefined);
  }
}

export type EnableResult = { ok: true; reminder: Reminder } | { ok: false; message: string };

/** Turns the reminder on at this time (or moves it), asking for permission the first time. */
export async function enableReminder(hour: number, minute: number): Promise<EnableResult> {
  if (Platform.OS === "android") {
    // The permission prompt on Android 13+ only appears once a channel exists.
    await Notifications.setNotificationChannelAsync(CHANNEL, {
      name: "Daily study reminder",
      importance: AndroidImportance.DEFAULT,
    });
  }
  let { status } = await Notifications.getPermissionsAsync();
  if (status !== "granted") {
    ({ status } = await Notifications.requestPermissionsAsync());
  }
  if (status !== "granted") {
    return {
      ok: false,
      message: "Notifications are turned off for this app. Allow them in Android settings.",
    };
  }

  const previous = await load();
  await cancel(previous.notificationId);
  const notificationId = await Notifications.scheduleNotificationAsync({
    content: {
      title: "Time for German",
      body: "Your plan for today is ready. Open the app to see what to study.",
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DAILY,
      hour,
      minute,
      channelId: CHANNEL,
    },
  });
  const reminder = { enabled: true, hour, minute, notificationId };
  await save(reminder);
  return { ok: true, reminder };
}

export async function disableReminder(): Promise<Reminder> {
  const previous = await load();
  await cancel(previous.notificationId);
  const reminder = { ...previous, enabled: false, notificationId: null };
  await save(reminder);
  return reminder;
}

/** On sign out: the reminder belongs to the account, so it goes with it. */
export async function clearReminder(): Promise<void> {
  const previous = await load();
  await cancel(previous.notificationId);
  await AsyncStorage.removeItem(KEY).catch(() => undefined);
}

export function useReminder() {
  const [reminder, setReminder] = useState<Reminder>(DEFAULT_REMINDER);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void load().then(setReminder);
  }, []);

  const enable = useCallback(async (hour: number, minute: number) => {
    setBusy(true);
    setError(null);
    try {
      const result = await enableReminder(hour, minute);
      if (result.ok) setReminder(result.reminder);
      else setError(result.message);
    } catch {
      setError("Could not set the reminder. Please try again.");
    } finally {
      setBusy(false);
    }
  }, []);

  const disable = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setReminder(await disableReminder());
    } finally {
      setBusy(false);
    }
  }, []);

  return { reminder, error, busy, enable, disable };
}
