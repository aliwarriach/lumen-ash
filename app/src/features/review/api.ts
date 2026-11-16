import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import { flushOutbox, pendingCount, subscribe, type FlushResult } from "@/features/review/outbox";
import { deviceTimezone } from "@/lib/timezone";

export type QueueCard = components["schemas"]["QueueCard"];
export type Queue = components["schemas"]["QueueOut"];

export const QUEUE_KEY = ["reviews", "queue"] as const;

export function useReviewQueue() {
  return useQuery({
    queryKey: QUEUE_KEY,
    queryFn: async () =>
      unwrap(await api.GET("/reviews/queue", { params: { query: { tz: deviceTimezone() } } })),
    // Kept on the phone (see the root layout) so reviews work offline or while the server wakes.
    gcTime: 24 * 60 * 60_000,
  });
}

/** Number of answers saved on the phone but not uploaded yet. */
export function usePendingReviews(): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    void pendingCount().then(setCount);
    return subscribe(setCount);
  }, []);
  return count;
}

/** Uploads saved answers now, when the app returns to the foreground, and on demand. */
export function useOutboxSync() {
  const queryClient = useQueryClient();
  const flush = useCallback(async (): Promise<FlushResult> => {
    const result = await flushOutbox();
    if (result.sent.length || result.rejected.length) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["reviews"] }),
        queryClient.invalidateQueries({ queryKey: ["words"] }),
        queryClient.invalidateQueries({ queryKey: ["chapters"] }),
        queryClient.invalidateQueries({ queryKey: ["grammar"] }),
        queryClient.invalidateQueries({ queryKey: ["mistakes"] }),
      ]);
    }
    return result;
  }, [queryClient]);

  useEffect(() => {
    void flush();
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") void flush();
    });
    return () => sub.remove();
  }, [flush]);

  return flush;
}

export const STAGE_EXPLANATIONS: Record<components["schemas"]["WordStage"], string> = {
  new: "Not reviewed yet.",
  learning: "In your first reviews.",
  familiar: "You recognise it and have produced it correctly.",
  usable: "You can produce it reliably over at least a week.",
  mastered: "You used it correctly in your own sentences on 2 different days.",
};
