import { router } from "expo-router";
import { ActivityIndicator, FlatList, RefreshControl, View } from "react-native";

import { STATUS_LABELS, useChapters, type ChapterSummary } from "@/features/course/api";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, Loading, Pill, ProgressBar } from "@/ui/components";
import { Check, ChevronRight, ICON } from "@/ui/icons";
import { makeStyles, space, useTheme, type Accent } from "@/ui/theme";

export default function CourseMap() {
  const styles = useStyles();
  const colors = useTheme();
  const chapters = useChapters();
  // The chapter to work on now (the first one not finished) is the one glass card on the page.
  const current = chapters.data?.find((c) => c.progress.status !== "completed")?.id;

  return (
    <>
      {chapters.isPending ? (
        // The free server may take up to a minute to wake up.
        <Centered>
          <ActivityIndicator color={colors.primary} />
          <Loading label="Loading your course…" />
        </Centered>
      ) : chapters.isError ? (
        <Centered>
          <ErrorText error={chapters.error} />
          <Button label="Try again" variant="secondary" onPress={() => chapters.refetch()} />
        </Centered>
      ) : (
        <FlatList
          data={chapters.data}
          keyExtractor={(c) => c.id}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={chapters.isRefetching}
              onRefresh={() => void chapters.refetch()}
            />
          }
          renderItem={({ item }) => <ChapterRow chapter={item} current={item.id === current} />}
          ListEmptyComponent={
            <Card>
              <Text style={styles.title}>No chapters yet</Text>
              <Text style={styles.muted}>
                Add the chapters of your course, then attach book pages, Allango audio and
                workbook exercises to each one.
              </Text>
            </Card>
          }
          ListFooterComponent={
            <Button label="Add chapter" onPress={() => router.push("/chapters/new")} />
          }
        />
      )}
    </>
  );
}

function ChapterRow({ chapter, current }: { chapter: ChapterSummary; current: boolean }) {
  const styles = useStyles();
  const colors = useTheme();
  const { total, completed, status } = chapter.progress;
  const accent: Accent =
    status === "completed"
      ? colors.green
      : status === "in_progress"
        ? { fg: colors.onPrimaryContainer, bg: colors.primaryContainer }
        : { fg: colors.muted, bg: colors.well };
  const progress = total
    ? `${completed} of ${total} done`
    : "No resources added yet";
  const words =
    chapter.words.total > 0 ? ` · ${chapter.words.mastered} of ${chapter.words.total} words mastered` : "";
  return (
    <Card
      glass={current}
      onPress={() => router.push({ pathname: "/chapters/[id]", params: { id: chapter.id } })}
      label={`Kapitel ${chapter.number}, ${chapter.title}. ${STATUS_LABELS[status]}. ${progress}${words}`}
    >
      <View style={styles.rowHeader}>
        <Text style={styles.number}>Kapitel {chapter.number}</Text>
        <Pill
          label={STATUS_LABELS[status]}
          accent={accent}
          icon={status === "completed" ? Check : undefined}
        />
      </View>
      <View style={styles.titleRow}>
        <Text style={styles.title}>{chapter.title}</Text>
        <ChevronRight size={ICON.bar} color={colors.muted} />
      </View>
      {chapter.topics.length > 0 && (
        <Text style={styles.muted} numberOfLines={2}>
          {chapter.topics.join(" · ")}
        </Text>
      )}
      <ProgressBar value={total ? completed / total : 0} color={colors.done} label={`Kapitel ${chapter.number} progress`} />
      <Text style={styles.muted}>
        {progress}
        {words}
      </Text>
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  list: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  rowHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  number: { fontSize: 13, lineHeight: 18, fontWeight: "800", color: colors.muted, letterSpacing: 0.4 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: space.sm },
  title: { flex: 1, fontSize: 17, lineHeight: 24, fontWeight: "800" },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted, textAlign: "left" },
}));
