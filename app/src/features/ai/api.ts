import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type AiQuota = Schemas["QuotaOut"];
export type FeatureQuota = Schemas["FeatureQuotaOut"];

/** What the learner has left today. Calls no AI, so it is safe to refetch often. */
export function useAiQuota() {
  return useQuery({
    queryKey: ["ai", "quota"],
    queryFn: async () => unwrap(await api.GET("/ai/quota")),
    staleTime: 60_000,
  });
}

/** "8 sentence checks left today" */
export function remainingText(feature: FeatureQuota): string {
  const left = feature.remaining;
  if (left === 0) return `No ${feature.label} left today`;
  return `${left} ${feature.label} left today`;
}
