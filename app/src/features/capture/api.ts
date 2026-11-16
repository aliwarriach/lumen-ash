import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import { deviceTimezone } from "@/lib/timezone";

type Schemas = components["schemas"];
export type ClassTask = Schemas["ClassTaskOut"];
export type ClassTaskInput = Schemas["ClassTaskIn"];
export type TaskKind = Schemas["TaskKind"];
export type ScanResult = Schemas["ScanOut"];
export type ProposedTask = Schemas["ProposedTaskOut"];

export const KIND_LABELS: Record<TaskKind, string> = {
  homework: "Homework",
  deadline: "Deadline",
  test: "Test",
  event: "Event",
  other: "Other",
};

const keys = {
  all: ["class-tasks"] as const,
  list: (includeDone: boolean) => ["class-tasks", { includeDone }] as const,
};

/** Open tasks (soonest due first), and with `includeDone` the ones finished in the last 14 days. */
export function useClassTasks(includeDone = false) {
  return useQuery({
    queryKey: keys.list(includeDone),
    queryFn: async () =>
      unwrap(
        await api.GET("/class-tasks", {
          params: { query: { include_done: includeDone, tz: deviceTimezone() } },
        }),
      ),
  });
}

/** Tasks, the Today plan and the AI allowance all change together. */
function useRefresh() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.all }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
}

/** Asks the AI what the message says to do. Saves nothing. */
export function useScanMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(await api.POST("/capture/scan", { body: { text }, params: { query: { tz: deviceTimezone() } } })),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["ai", "quota"] }), // "7 message scans left"
  });
}

export function useCreateTasks() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (items: ClassTaskInput[]) =>
      unwrap(
        await api.POST("/class-tasks", {
          body: { items },
          params: { query: { tz: deviceTimezone() } },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useUpdateTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (v: { id: string; changes: Schemas["ClassTaskUpdate"] }) =>
      unwrap(
        await api.PATCH("/class-tasks/{task_id}", {
          params: { path: { task_id: v.id }, query: { tz: deviceTimezone() } },
          body: v.changes,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.DELETE("/class-tasks/{task_id}", { params: { path: { task_id: id } } })),
    onSuccess: refresh,
  });
}

/** "Thu 12 Nov" for a YYYY-MM-DD date. */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** "Due tomorrow · Fri 13 Nov", "2 days overdue · Sun 8 Nov", or "No date". */
export function dueLabel(task: Pick<ClassTask, "due_date" | "days_left">): string {
  if (!task.due_date || task.days_left === null) return "No date";
  const when = formatDate(task.due_date);
  const left = task.days_left;
  if (left < -1) return `${-left} days overdue · ${when}`;
  if (left === -1) return `Due yesterday · ${when}`;
  if (left === 0) return `Due today · ${when}`;
  if (left === 1) return `Due tomorrow · ${when}`;
  return `Due in ${left} days · ${when}`;
}
