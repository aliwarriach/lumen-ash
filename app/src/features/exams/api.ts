import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { components } from "@/api/schema";
import { deviceTimezone } from "@/lib/timezone";
import type { ColorToken } from "@/ui/theme";

type Schemas = components["schemas"];
export type Exam = Schemas["ExamOut"];
export type ExamDetail = Schemas["ExamDetailOut"];
export type ExamInput = Schemas["ExamCreate"];
export type ExamKind = Schemas["ExamKind"];
export type ExamResult = Schemas["ResultOut"];
export type ResultInput = Schemas["ResultCreate"];
export type ResultKind = Schemas["ResultKind"];
export type Skill = Schemas["Skill"];
export type Verdict = Schemas["Verdict"];
export type Readiness = Schemas["ReadinessOut"];
export type ChapterReadiness = Schemas["ChapterReadinessOut"];
export type SkillReadiness = Schemas["SkillOut"];

const keys = {
  all: ["exams"] as const,
  list: ["exams", "list"] as const,
  one: (id: string) => ["exams", id] as const,
};

export const KIND_LABELS: Record<ExamKind, string> = {
  internal: "Internal ASH test",
  goethe_a1: "Goethe A1 exam",
};

export const SKILL_LABELS: Record<Skill, string> = {
  reading: "Reading",
  listening: "Listening",
  writing: "Writing",
  speaking: "Speaking",
  vocabulary: "Vocabulary",
  grammar: "Grammar",
};

/** Names of palette colors: look them up with `useTheme()`. */
export const VERDICT_COLORS: Record<Verdict, ColorToken> = {
  ready: "success",
  almost: "warning",
  not_ready: "danger",
  unknown: "muted",
};

export const VERDICT_LABELS: Record<Verdict, string> = {
  ready: "Looking ready",
  almost: "Almost ready",
  not_ready: "Not ready yet",
  unknown: "Not enough information",
};

export function useExams() {
  return useQuery({
    queryKey: keys.list,
    queryFn: async () =>
      unwrap(await api.GET("/exams", { params: { query: { tz: deviceTimezone() } } })),
  });
}

export function useExam(id: string) {
  return useQuery({
    queryKey: keys.one(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/exams/{exam_id}", {
          params: { path: { exam_id: id }, query: { tz: deviceTimezone() } },
        }),
      ),
  });
}

/** Tests, results, the Today screen and the plan all depend on each other. */
function useRefreshExams() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.all }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
}

export function useCreateExam() {
  const refresh = useRefreshExams();
  return useMutation({
    mutationFn: async (body: ExamInput) =>
      unwrap(await api.POST("/exams", { body, params: { query: { tz: deviceTimezone() } } })),
    onSuccess: refresh,
  });
}

export function useDeleteExam(id: string) {
  const refresh = useRefreshExams();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.DELETE("/exams/{exam_id}", { params: { path: { exam_id: id } } })),
    onSuccess: refresh,
  });
}

export function useCreateResult() {
  const refresh = useRefreshExams();
  return useMutation({
    mutationFn: async (body: ResultInput) => unwrap(await api.POST("/exam-results", { body })),
    onSuccess: refresh,
  });
}

export function useDeleteResult() {
  const refresh = useRefreshExams();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.DELETE("/exam-results/{result_id}", { params: { path: { result_id: id } } }),
      ),
    onSuccess: refresh,
  });
}

/** "In 9 days", "Tomorrow", "Today", "3 days ago". */
export function countdown(daysLeft: number): string {
  if (daysLeft === 0) return "Today";
  if (daysLeft === 1) return "Tomorrow";
  if (daysLeft > 1) return `In ${daysLeft} days`;
  return daysLeft === -1 ? "Yesterday" : `${-daysLeft} days ago`;
}

/** The learner's local date as YYYY-MM-DD, `offsetDays` from today. */
export function isoDate(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** True for a real calendar date written as YYYY-MM-DD. */
export function isValidIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d;
}
