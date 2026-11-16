import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import { deviceTimezone } from "@/lib/timezone";
import type { ColorToken } from "@/ui/theme";

type Schemas = components["schemas"];
export type Dashboard = Schemas["DashboardOut"];
export type PlanItem = Schemas["PlanItemOut"];
export type TrackStatus = Schemas["TrackStatus"];

export const DASHBOARD_KEY = ["dashboard"] as const;

/** Everything on the Today screen, in one request. Kept on the phone for offline use. */
export function useDashboard() {
  return useQuery({
    queryKey: DASHBOARD_KEY,
    queryFn: async () =>
      unwrap(await api.GET("/dashboard", { params: { query: { tz: deviceTimezone() } } })),
    gcTime: 24 * 60 * 60_000,
    // The plan changes as the learner studies, so look again when they come back to the screen.
    staleTime: 10_000,
  });
}

export const STATUS_TEXT: Record<TrackStatus, string> = {
  getting_started: "Getting started",
  on_track: "On track",
  slipping: "Slipping",
};

/** Names of palette colors: look them up with `useTheme()`. */
export const STATUS_COLORS: Record<TrackStatus, ColorToken> = {
  getting_started: "primary",
  on_track: "success",
  slipping: "warning",
};

/** The learner's local date as YYYY-MM-DD, to tell whether a saved plan is from today. */
export function localToday(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
