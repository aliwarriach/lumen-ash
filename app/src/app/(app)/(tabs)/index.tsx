import { useQueryClient } from "@tanstack/react-query";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { Linking, Pressable, RefreshControl, ScrollView, View } from "react-native";
import Animated from "react-native-reanimated";

import { useUpdateTask } from "@/features/capture/api";
import { DASHBOARD_KEY, localToday, useDashboard, type Dashboard, type PlanItem } from "@/features/dashboard/api";
import { useTicks } from "@/features/dashboard/ticks";
import { greeting, isDone, nextBadge, nextItem, weekStrip } from "@/features/dashboard/today";
import { TodayIllustration } from "@/features/dashboard/TodayIllustration";
import { VERDICT_COLORS, countdown } from "@/features/exams/api";
import { ProgressRing } from "@/ui/ProgressRing";
import { Text } from "@/ui/Text";
import { Button, Centered, ErrorText, Loading, ProgressBar, TextLink } from "@/ui/components";
import { Glass } from "@/ui/glass";
import { ArrowRight, Award, BookA, Check, Copy, Flag, Flame, ICON, type Icon } from "@/ui/icons";
import { usePop } from "@/ui/motion";
import { makeStyles, radius, space, TOUCH, useTheme, type Accent } from "@/ui/theme";

/**
 * Today, as approved for the glass restyle: one glass main card with the one primary action
 * (Continue), then flat sections (numbers, this week, the next badge), the plan in glass, and the
 * next test. Grammar, tools, community and account are in the drawer (the ⋮ button).
 */
export default function Today() {
  const styles = useStyles();
  const queryClient = useQueryClient();
  const board = useDashboard();
  const { ticked, toggle } = useTicks(board.data?.date);
  const finishTask = useUpdateTask();

  // Come back from a review or a chapter and the plan is up to date.
  useFocusEffect(
    useCallback(() => {
      void queryClient.invalidateQueries({ queryKey: DASHBOARD_KEY });
    }, [queryClient]),
  );

  if (!board.data) {
    return (
      <Centered>
        {board.isError ? <ErrorText error={board.error} /> : <Loading label="Loading your plan…" />}
      </Centered>
    );
  }

  const data = board.data;
  const stale = data.date !== localToday();
  const onTick = (item: PlanItem) =>
    item.kind === "class_task" && item.class_task_id
      ? // Class tasks are saved on the server, so ticking one saves it there.
        finishTask.mutate({ id: item.class_task_id, changes: { done: !isDone(item, ticked) } })
      : toggle(item.id);

  return (
    <ScrollView
      contentContainerStyle={styles.page}
      refreshControl={
        <RefreshControl refreshing={board.isRefetching} onRefresh={() => void board.refetch()} />
      }
    >
      {(stale || board.isError) && (
        <Text style={styles.note} accessibilityLiveRegion="polite">
          {board.isError
            ? "Can't reach the server. Showing what was saved on this phone."
            : "Showing your last saved plan."}
        </Text>
      )}
      <MainCard data={data} ticked={ticked} />
      <Numbers data={data} />
      <ThisWeek data={data} />
      <BadgeRow data={data} />
      <Plan data={data} ticked={ticked} onTick={onTick} />
      <NextTest data={data} />
    </ScrollView>
  );
}

/** Opens a plan item where it is done: a tab, a screen, or the class's link. */
function open(item: PlanItem) {
  switch (item.kind) {
    case "review":
      router.navigate("/review");
      break;
    case "grammar":
      if (item.pattern_key) {
        router.push({ pathname: "/grammar/[key]", params: { key: item.pattern_key } });
      }
      break;
    case "writing":
      router.navigate("/write");
      break;
    case "class_task":
      if (item.url) void Linking.openURL(item.url);
      else router.push("/capture");
      break;
    case "exam":
    case "homework":
    case "listening":
      if (item.url) void Linking.openURL(item.url);
      else if (item.chapter_id) {
        router.push({ pathname: "/chapters/[id]", params: { id: item.chapter_id } });
      }
      break;
  }
}

// The glass main card: greeting, picture, today's progress and the one primary action.
function MainCard({ data, ticked }: { data: Dashboard; ticked: string[] }) {
  const styles = useStyles();
  const items = data.plan.items;
  const done = items.filter((i) => isDone(i, ticked)).length;
  const minutesLeft = items.filter((i) => !isDone(i, ticked)).reduce((sum, i) => sum + i.minutes, 0);
  const next = nextItem(items, ticked);
  return (
    <Glass style={styles.main}>
      <View style={styles.hello}>
        <View style={styles.helloText}>
          <Text style={styles.greeting} accessibilityRole="header">
            {greeting(new Date().getHours())}
          </Text>
          <Text style={styles.secondary}>{data.on_track.reason}</Text>
        </View>
        <TodayIllustration />
      </View>
      {items.length > 0 && (
        <View style={styles.progress}>
          <ProgressRing
            value={done / items.length}
            label={`Today's plan: ${done} of ${items.length} done`}
          >
            <Text style={styles.ringText}>
              {done}/{items.length}
            </Text>
          </ProgressRing>
          <View style={styles.progressText}>
            <Text style={styles.sectionTitle}>Today&apos;s plan</Text>
            <Text style={styles.secondary}>
              {minutesLeft === 0 ? "All done for today. Gut gemacht!" : `About ${minutesLeft} minutes left`}
            </Text>
          </View>
        </View>
      )}
      {next && <Button label={`Continue: ${next.title}`} icon={ArrowRight} onPress={() => open(next)} />}
    </Glass>
  );
}

// Four numbers, flat: each an icon in a tinted circle with its value and label.
function Numbers({ data }: { data: Dashboard }) {
  const colors = useTheme();
  const styles = useStyles();
  const stats: { icon: Icon; accent: Accent; value: string; label: string }[] = [
    { icon: Flame, accent: colors.amber, value: String(data.on_track.streak), label: "day streak" },
    {
      icon: Copy,
      accent: { fg: colors.onPrimaryContainer, bg: colors.primaryContainer },
      value: String(data.cards.due),
      label: "cards due",
    },
    { icon: BookA, accent: colors.green, value: String(data.vocabulary.mastered), label: "words known" },
    {
      icon: Flag,
      accent: colors.teal,
      value: `${data.chapters.completed}/${data.chapters.total}`,
      label: "chapters",
    },
  ];
  return (
    <View style={styles.stats} accessibilityLabel="Your numbers">
      {stats.map(({ icon: StatIcon, accent, value, label }) => (
        <View key={label} style={styles.stat} accessible accessibilityLabel={`${value} ${label}`}>
          <View style={[styles.statIcon, { backgroundColor: accent.bg }]}>
            <StatIcon size={ICON.mark} color={accent.fg} />
          </View>
          <Text style={styles.statValue}>{value}</Text>
          <Text style={styles.label}>{label}</Text>
        </View>
      ))}
    </View>
  );
}

// Monday to Sunday, flat: a finished day is filled amber with a tick, today has a ring.
function ThisWeek({ data }: { data: Dashboard }) {
  const colors = useTheme();
  const styles = useStyles();
  const days = weekStrip(data.on_track.week, data.date);
  const studied = days.filter((d) => d.done);
  const said =
    studied.length === 0 ? "nothing yet" : `studied on ${studied.map((d) => d.name).join(", ")}`;
  return (
    <View style={styles.section}>
      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle} accessibilityRole="header">
          This week
        </Text>
        <Text style={[styles.small, { color: colors.amber.fg }]}>
          {studied.length} of 7 days
        </Text>
      </View>
      <View style={styles.week} accessible accessibilityLabel={`This week: ${said}.`}>
        {days.map((d) => (
          <View key={d.label} style={styles.day}>
            <View style={[styles.dayDot, d.done && styles.dayDone, d.today && styles.dayToday]}>
              {d.done && <Check size={ICON.badge} strokeWidth={3} color={colors.onWeekDone} />}
            </View>
            <Text style={[styles.label, d.today && styles.todayLabel]}>{d.label}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

// One slim outlined row: a badge earned today, or the next one to aim for.
function BadgeRow({ data }: { data: Dashboard }) {
  const colors = useTheme();
  const styles = useStyles();
  const badge = nextBadge(data);
  // A badge earned today pops once when Today opens. Nothing else on this screen moves but the ring.
  const pop = usePop(Boolean(badge?.isNew));
  if (!badge) return null;
  return (
    <View
      style={styles.badge}
      accessible
      accessibilityLabel={`${badge.isNew ? "New badge" : "Next badge"}: ${badge.title}. ${badge.detail}`}
    >
      <Animated.View style={[styles.badgeIcon, { backgroundColor: colors.orange.bg }, pop]}>
        <Award size={ICON.large} color={colors.orange.fg} />
      </Animated.View>
      <View style={styles.badgeText}>
        <Text style={styles.bodyStrong}>
          {badge.isNew ? "New badge" : "Next badge"}: {badge.title}
        </Text>
        <Text style={styles.small2}>{badge.detail}</Text>
      </View>
      {!badge.isNew && <Text style={styles.badgeProgress}>{badge.progress}</Text>}
    </View>
  );
}

// What to do today: the plan in glass, one row per item.
function Plan({
  data,
  ticked,
  onTick,
}: {
  data: Dashboard;
  ticked: string[];
  onTick: (item: PlanItem) => void;
}) {
  const styles = useStyles();
  const items = data.plan.items;
  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, styles.inset]} accessibilityRole="header">
        What to do today
      </Text>
      {items.length > 0 && (
        <Glass style={styles.planCard} rounded={radius.lg}>
          {items.map((item, i) => (
            <PlanRow
              key={item.id}
              item={item}
              first={i === 0}
              done={isDone(item, ticked)}
              onTick={() => onTick(item)}
            />
          ))}
        </Glass>
      )}
      {data.plan.note && <Text style={[styles.small2, styles.inset]}>{data.plan.note}</Text>}
    </View>
  );
}

function PlanRow({
  item,
  first,
  done,
  onTick,
}: {
  item: PlanItem;
  first: boolean;
  done: boolean;
  onTick: () => void;
}) {
  const colors = useTheme();
  const styles = useStyles();
  // The learner ticks what the app can't see (listening, speaking) and their class tasks;
  // the rest the app ticks itself when the work is done.
  const manual = item.done === null || item.kind === "class_task";
  return (
    <View style={[styles.planRow, !first && styles.planDivider]}>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: done, disabled: !manual }}
        accessibilityLabel={manual ? `Mark "${item.title}" as done` : `${item.title}, ticked by the app`}
        disabled={!manual}
        onPress={onTick}
        android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
        style={[styles.box, manual && styles.boxManual, done && styles.boxDone]}
      >
        {done && <Check size={ICON.mark} strokeWidth={3} color={colors.onDone} />}
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityHint="Opens it"
        onPress={() => open(item)}
        android_ripple={{ color: colors.divider }}
        style={styles.planOpen}
      >
        <View style={styles.planText}>
          <Text style={[styles.bodyStrong, done && styles.doneText]}>{item.title}</Text>
          <Text style={styles.small2}>{item.why}</Text>
        </View>
        <Text style={styles.minutes}>{item.minutes} min</Text>
      </Pressable>
    </View>
  );
}

// The next test, flat: countdown and a readiness bar.
function NextTest({ data }: { data: Dashboard }) {
  const colors = useTheme();
  const styles = useStyles();
  const next = data.test.next;
  if (!next) {
    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle} accessibilityRole="header">
          Next test
        </Text>
        <Text style={styles.small2}>{data.test.message}</Text>
        <TextLink label="Add a test" onPress={() => router.push("/exams")} />
      </View>
    );
  }
  const estimate = next.estimate ?? null;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint="Shows why, and what to revise"
      onPress={() => router.push({ pathname: "/exams/[id]", params: { id: next.id } })}
      android_ripple={{ color: colors.divider }}
      style={styles.section}
    >
      <View style={styles.sectionHead}>
        <Text style={[styles.sectionTitle, styles.shrink]} accessibilityRole="header">
          {next.title}
        </Text>
        <Text style={styles.countdown}>{countdown(next.days_left)}</Text>
      </View>
      {estimate !== null && (
        <ProgressBar
          value={estimate / 100}
          color={colors.illustration.teal}
          label={`Readiness ${Math.round(estimate)}%`}
        />
      )}
      <Text style={[styles.small2, { color: colors[VERDICT_COLORS[next.verdict]] }]}>
        {estimate !== null ? `Readiness ${Math.round(estimate)}%: ` : ""}
        {next.headline}
      </Text>
      {next.scope_note && <Text style={styles.small2}>{next.scope_note}</Text>}
    </Pressable>
  );
}

const DOT = 36;

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.section },
  note: { fontSize: 14, lineHeight: 20, fontWeight: "600", color: colors.warning },
  // Text styles from the type scale.
  greeting: { fontSize: 26, lineHeight: 32, fontWeight: "800" },
  sectionTitle: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  bodyStrong: { fontSize: 16, lineHeight: 22, fontWeight: "700" },
  secondary: { fontSize: 15, lineHeight: 21, color: colors.muted },
  small: { fontSize: 14, lineHeight: 20, fontWeight: "600" },
  small2: { fontSize: 14, lineHeight: 20, color: colors.muted },
  label: { fontSize: 13, lineHeight: 18, color: colors.muted },
  shrink: { flexShrink: 1 },
  inset: { marginHorizontal: space.xs },
  // Main card.
  main: { padding: space.lg + space.xs, gap: space.lg + 2 },
  hello: { flexDirection: "row", alignItems: "center", gap: space.md },
  helloText: { flex: 1, gap: space.xs },
  progress: { flexDirection: "row", alignItems: "center", gap: space.lg },
  progressText: { flex: 1, gap: 2 },
  ringText: { fontSize: 20, lineHeight: 26, fontWeight: "800" },
  // Numbers.
  stats: { flexDirection: "row", gap: space.sm },
  stat: { flex: 1, alignItems: "center", gap: 6 },
  statIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  statValue: { fontSize: 17, lineHeight: 22, fontWeight: "800" },
  // Sections that sit flat on the page.
  section: { gap: space.md - 2 },
  sectionHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    gap: space.md,
    marginHorizontal: space.xs,
  },
  // This week.
  week: { flexDirection: "row", justifyContent: "space-between", marginHorizontal: space.xs },
  day: { alignItems: "center", gap: 6 },
  dayDot: {
    width: DOT,
    height: DOT,
    borderRadius: DOT / 2,
    backgroundColor: colors.well,
    alignItems: "center",
    justifyContent: "center",
  },
  dayDone: { backgroundColor: colors.weekDone },
  dayToday: { borderWidth: 2, borderColor: colors.primary },
  todayLabel: { color: colors.onPrimaryContainer, fontWeight: "700" },
  // Badge.
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md + 2,
    paddingVertical: space.md + 2,
    paddingHorizontal: space.lg,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.divider,
    backgroundColor: colors.flat,
  },
  badgeIcon: { width: TOUCH, height: TOUCH, borderRadius: TOUCH / 2, alignItems: "center", justifyContent: "center" },
  badgeText: { flex: 1, gap: 2 },
  badgeProgress: { fontSize: 14, lineHeight: 20, fontWeight: "700", color: colors.muted },
  // Plan.
  planCard: { padding: 0, paddingVertical: space.xs, gap: 0 },
  planRow: { flexDirection: "row", alignItems: "center", paddingLeft: space.md + 2 },
  planDivider: { borderTopWidth: 1, borderTopColor: colors.divider },
  box: {
    width: TOUCH,
    height: TOUCH,
    borderRadius: radius.md,
    backgroundColor: colors.well,
    alignItems: "center",
    justifyContent: "center",
  },
  boxManual: { borderWidth: 1.5, borderColor: colors.border },
  boxDone: { backgroundColor: colors.done, borderColor: colors.done },
  planOpen: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    minHeight: TOUCH + 20,
    paddingVertical: space.sm + 2,
    paddingLeft: space.md,
    paddingRight: space.md + 2,
  },
  planText: { flex: 1, gap: 2 },
  minutes: { fontSize: 14, lineHeight: 20, fontWeight: "600", color: colors.muted },
  doneText: { textDecorationLine: "line-through", color: colors.muted },
  // Next test.
  countdown: { fontSize: 15, lineHeight: 22, fontWeight: "800", color: colors.onPrimaryContainer },
}));
