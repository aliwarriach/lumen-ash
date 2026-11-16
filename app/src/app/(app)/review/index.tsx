import { router, useFocusEffect, type Href } from "expo-router";
import { useCallback, type ReactNode } from "react";
import { ActivityIndicator, Pressable, RefreshControl, View } from "react-native";

import { useProgressReview, type Metric, type Step, type Tone } from "@/features/progress/api";
import { useOutboxSync, usePendingReviews, useReviewQueue } from "@/features/review/api";
import { Check, ChevronRight, Dumbbell, Hand, ICON, PartyPopper, Rocket, ThumbsUp, type Icon } from "@/ui/icons";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, ErrorText, IconLabel, ProgressBar } from "@/ui/components";
import { Glass } from "@/ui/glass";
import { type Accent, type Palette, makeStyles, space, TOUCH, useTheme } from "@/ui/theme";

/** The headline's picture and color: an icon in a tinted circle, never color alone. */
const TONE: Record<Tone, { icon: Icon; accent: (colors: Palette) => Accent }> = {
  start: { icon: Rocket, accent: primaryAccent },
  welcome_back: { icon: Hand, accent: primaryAccent },
  great: { icon: PartyPopper, accent: (c) => c.green },
  good: { icon: ThumbsUp, accent: primaryAccent },
  keep_going: { icon: Dumbbell, accent: (c) => c.amber },
};

function primaryAccent(c: Palette): Accent {
  return { fg: c.onPrimaryContainer, bg: c.primaryContainer };
}

/**
 * Review: how you are doing. Today's cards at the top, then this week against last, what went
 * well, what is under way and what is next. Areas to improve live in the Mistake Log; this page
 * points there kindly. Written by plain rules from the learner's own records: no AI.
 */
export default function Review() {
  const colors = useTheme();
  const styles = useStyles();
  const queue = useReviewQueue();
  const progress = useProgressReview();
  const pending = usePendingReviews();
  const flush = useOutboxSync();

  // Lessons, practice and cards change the numbers: refresh whenever the tab is opened.
  useFocusEffect(
    useCallback(() => {
      void progress.refetch();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  );

  const q = queue.data;
  const cards = q ? q.due_count + q.new_count : 0;
  const p = progress.data;

  return (
    <FormScroll
      contentContainerStyle={styles.page}
      refreshControl={
        <RefreshControl
          refreshing={queue.isRefetching || progress.isRefetching}
          onRefresh={() => void flush().then(() => Promise.all([queue.refetch(), progress.refetch()]))}
        />
      }
    >
      {/* Today's cards stay first: spaced repetition is what makes words stick. */}
      <Glass>
        <View style={styles.cardsRow}>
          <View style={styles.flex}>
            <Text style={styles.label}>TODAY’S CARDS</Text>
            <Text style={styles.cardsCount} accessibilityRole="header">
              {q ? (cards === 0 ? "All done for now" : `${cards} to review`) : "…"}
            </Text>
            {q && cards > 0 && (
              <Text style={styles.muted}>
                {q.due_count} due · {q.new_count} new
              </Text>
            )}
          </View>
          {cards > 0 && <Button label="Start" onPress={() => router.push("/review/session")} />}
        </View>
        {queue.isError && <ErrorText error={queue.error} />}
      </Glass>

      {pending > 0 && (
        <Card>
          <Text style={styles.body}>
            {pending} answer{pending === 1 ? "" : "s"} saved on this phone, waiting to upload.
          </Text>
          <Button label="Upload now" variant="secondary" onPress={() => void flush()} />
        </Card>
      )}

      {progress.isPending && <ActivityIndicator color={colors.primary} />}
      {progress.isError && <ErrorText error={progress.error} />}
      {p && (
        <>
          <View style={styles.hero}>
            <ToneIcon icon={TONE[p.tone].icon} accent={TONE[p.tone].accent(colors)} />
            <View style={styles.flex}>
              <Text style={styles.headline} accessibilityRole="header">
                {p.headline}
              </Text>
              <Text style={styles.message}>{p.message}</Text>
            </View>
          </View>

          <Section title="This week">
            <View style={styles.metrics}>
              {p.this_week.map((m) => (
                <MetricTile key={m.label} metric={m} />
              ))}
            </View>
          </Section>

          {p.achievements.length > 0 && (
            <Section title="What went well">
              <Card>
                {p.achievements.map((a) => (
                  <IconLabel key={a} icon={Check} color={colors.success} style={styles.win}>
                    {a}
                  </IconLabel>
                ))}
              </Card>
            </Section>
          )}

          {p.in_progress.length > 0 && (
            <Section title="In progress">
              {p.in_progress.map((s) => (
                <StepRow key={s.title} step={s} />
              ))}
            </Section>
          )}

          {p.to_do.length > 0 && (
            <Section title="Next steps">
              {p.to_do.map((s) => (
                <StepRow key={s.title} step={s} next />
              ))}
            </Section>
          )}

          {p.improve && (
            <Section title="Areas to improve">
              <StepRow step={p.improve} />
            </Section>
          )}
        </>
      )}

      <Text style={styles.note}>
        Cards you get wrong come back within minutes; ones you know well come back after days,
        then weeks.
      </Text>
    </FormScroll>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const styles = useStyles();
  return (
    <View style={styles.sectionBlock}>
      <Text style={styles.section} accessibilityRole="header">
        {title}
      </Text>
      {children}
    </View>
  );
}

function ToneIcon({ icon: ToneGlyph, accent }: { icon: Icon; accent: Accent }) {
  const styles = useStyles();
  return (
    <View style={[styles.toneIcon, { backgroundColor: accent.bg }]}>
      <ToneGlyph size={ICON.large} color={accent.fg} />
    </View>
  );
}

function MetricTile({ metric: m }: { metric: Metric }) {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <View style={styles.metric} accessible accessibilityLabel={`${m.label}: ${m.value}. ${m.change}`}>
      <Text style={styles.metricValue}>{m.value}</Text>
      <Text style={styles.metricLabel}>{m.label}</Text>
      <Text style={[styles.metricChange, m.rising && { color: colors.success, fontWeight: "700" }]}>
        {m.change}
      </Text>
    </View>
  );
}

function StepRow({ step: s, next = false }: { step: Step; next?: boolean }) {
  const styles = useStyles();
  const colors = useTheme();
  const open = s.link ? () => router.push(s.link as Href) : undefined;
  return (
    <Pressable
      accessibilityRole={open ? "button" : undefined}
      disabled={!open}
      onPress={open}
      android_ripple={{ color: colors.divider }}
      style={styles.step}
    >
      <View style={styles.flex}>
        <Text style={styles.stepTitle}>{s.title}</Text>
        <Text style={styles.muted}>{s.detail}</Text>
        {s.progress !== null && (
          <View style={styles.bar}>
            <ProgressBar
              value={s.progress}
              color={colors.done}
              label={`${s.title}: ${Math.round(s.progress * 100)}%`}
            />
          </View>
        )}
      </View>
      {open && (
        <View style={styles.go}>
          {next && <Text style={styles.goText}>Go</Text>}
          <ChevronRight size={ICON.inline} color={colors.primary} />
        </View>
      )}
    </Pressable>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.section },
  flex: { flex: 1, gap: 2 },
  label: { fontSize: 13, lineHeight: 18, fontWeight: "800", color: colors.muted, letterSpacing: 0.4 },
  cardsRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  cardsCount: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  body: { fontSize: 16, lineHeight: 24 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  hero: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.lg,
    backgroundColor: colors.flat,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: space.lg + space.xs,
  },
  toneIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  headline: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  message: { fontSize: 16, lineHeight: 22 },
  sectionBlock: { gap: space.md - 2 },
  section: { fontSize: 17, lineHeight: 24, fontWeight: "800", marginHorizontal: space.xs },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  metric: {
    flexBasis: "47%",
    flexGrow: 1,
    backgroundColor: colors.flat,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: space.lg,
    gap: 2,
  },
  metricValue: { fontSize: 26, lineHeight: 32, fontWeight: "800" },
  metricLabel: { fontSize: 14, lineHeight: 20, fontWeight: "600" },
  metricChange: { fontSize: 13, lineHeight: 18, color: colors.muted },
  win: { fontSize: 15, lineHeight: 22, paddingVertical: 2 },
  step: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    minHeight: TOUCH + 8,
    backgroundColor: colors.flat,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingVertical: space.md,
    paddingHorizontal: space.lg,
    overflow: "hidden",
  },
  stepTitle: { fontSize: 16, lineHeight: 22, fontWeight: "700" },
  bar: { marginTop: space.sm },
  go: { flexDirection: "row", alignItems: "center", gap: 2 },
  goText: { fontSize: 15, lineHeight: 22, fontWeight: "800", color: colors.primary },
  note: { fontSize: 13, lineHeight: 18, color: colors.muted, marginHorizontal: space.xs },
}));
