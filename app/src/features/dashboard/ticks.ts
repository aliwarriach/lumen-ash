// Plan items the app can't track itself (listening, speaking) are ticked off by the learner.
// The ticks live on the phone and are kept per day, so tomorrow's plan starts fresh.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useState } from "react";

const KEY = "plan-ticks:v1";

type Stored = { date: string; ids: string[] };

async function load(date: string): Promise<string[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    const stored = raw ? (JSON.parse(raw) as Stored) : null;
    return stored && stored.date === date ? stored.ids : [];
  } catch {
    return [];
  }
}

export async function clearTicks(): Promise<void> {
  await AsyncStorage.removeItem(KEY).catch(() => undefined);
}

/** The ids the learner has ticked on `date`, and a function to tick or untick one. */
export function useTicks(date: string | undefined) {
  const [ids, setIds] = useState<string[]>([]);

  useEffect(() => {
    if (date) void load(date).then(setIds);
  }, [date]);

  const toggle = useCallback(
    (id: string) => {
      if (!date) return;
      setIds((current) => {
        const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
        void AsyncStorage.setItem(KEY, JSON.stringify({ date, ids: next } satisfies Stored)).catch(
          () => undefined,
        );
        return next;
      });
    },
    [date],
  );

  return { ticked: ids, toggle };
}
