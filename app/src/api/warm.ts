// The free server sleeps after a quiet spell and takes up to a minute to wake. Pinging it as the
// app opens (and when it comes back to the foreground) means that wait happens while the learner
// is still looking at the Today screen, not in the middle of their first review.
import { useEffect } from "react";
import { AppState } from "react-native";

import { env } from "@/lib/env";

const MIN_GAP_MS = 5 * 60_000;

export function useWarmServer(): void {
  useEffect(() => {
    let last = 0;
    const ping = () => {
      if (Date.now() - last < MIN_GAP_MS) return;
      last = Date.now();
      void fetch(`${env.apiUrl}/health`).catch(() => undefined); // no answer is fine: it is a nudge
    };
    ping();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") ping();
    });
    return () => subscription.remove();
  }, []);
}
