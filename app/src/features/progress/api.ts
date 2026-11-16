import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import { deviceTimezone } from "@/lib/timezone";

type Schemas = components["schemas"];
export type ProgressReview = Schemas["ProgressReviewOut"];
export type Step = Schemas["StepOut"];
export type Metric = Schemas["MetricOut"];
export type Tone = Schemas["Tone"];

export function useProgressReview() {
  return useQuery({
    queryKey: ["progress", "review"],
    queryFn: async () =>
      unwrap(await api.GET("/progress/review", { params: { query: { tz: deviceTimezone() } } })),
  });
}
