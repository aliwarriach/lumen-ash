import { Stack, router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, Linking, Pressable, View } from "react-native";

import {
  STATUS_LABELS,
  kindLabel,
  useChapter,
  useDeleteChapter,
  useDeleteResource,
  useUpdateResource,
  type Resource,
} from "@/features/course/api";
import { AskCommunityButton } from "@/features/community/AskCommunity";
import { aboutChapter } from "@/features/community/ask";
import { LEVEL_COLORS, percent, usePatterns } from "@/features/grammar/api";
import { canShowInApp } from "@/features/player/policy";
import { WordRow } from "@/features/vocabulary/WordRow";
import { useWords } from "@/features/vocabulary/api";
import { Check, ChevronRight, ICON } from "@/ui/icons";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, Pill, ProgressBar, SectionTitle, TextLink } from "@/ui/components";
import { makeStyles, radius, space, TOUCH, useTheme, type Accent } from "@/ui/theme";

export default function ChapterDetail() {
  const colors = useTheme();
  const styles = useStyles();
  const { id } = useLocalSearchParams<{ id: string }>();
  const chapter = useChapter(id);
  const deleteChapter = useDeleteChapter(id);
  const words = useWords({ chapterId: id });
  const grammar = usePatterns(id);

  if (chapter.isPending) {
    return (
      <Centered>
        <ActivityIndicator color={colors.primary} />
      </Centered>
    );
  }
  if (chapter.isError) {
    return (
      <Centered>
        <ErrorText error={chapter.error} />
        <Button label="Try again" variant="secondary" onPress={() => chapter.refetch()} />
      </Centered>
    );
  }

  const c = chapter.data;
  const { total, completed, status } = c.progress;
  const statusAccent: Accent =
    status === "completed"
      ? colors.green
      : status === "in_progress"
        ? { fg: colors.onPrimaryContainer, bg: colors.primaryContainer }
        : { fg: colors.muted, bg: colors.well };

  function confirmDelete() {
    Alert.alert(`Delete Kapitel ${c.number}?`, "Its resources will be deleted too.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => deleteChapter.mutate(undefined, { onSuccess: () => router.back() }),
      },
    ]);
  }

  return (
    <>
      <Stack.Screen options={{ title: `Kapitel ${c.number}` }} />
      <FormScroll contentContainerStyle={styles.page}>
        <Card glass>
          <Pill label={STATUS_LABELS[status]} accent={statusAccent} icon={status === "completed" ? Check : undefined} />
          <Text style={styles.title} accessibilityRole="header">
            {c.title}
          </Text>
          <Text style={styles.muted}>
            {completed} of {total} done
          </Text>
          <ProgressBar value={total ? completed / total : 0} color={colors.done} label={`Chapter progress`} />
          {c.topics.length > 0 && (
            <View style={styles.topics}>
              {c.topics.map((t) => (
                <Text key={t} style={styles.topic}>
                  {t}
                </Text>
              ))}
            </View>
          )}
          {c.notes && <Text style={styles.body}>{c.notes}</Text>}
        </Card>

        <AskCommunityButton attachment={() => aboutChapter(c)} />

        <SectionTitle>Resources</SectionTitle>
        {c.resources.length === 0 ? (
          <Text style={styles.muted}>
            Add book pages, Allango audio and video links, and workbook exercises.
          </Text>
        ) : (
          c.resources.map((r) => <ResourceRow key={r.id} resource={r} />)
        )}

        <SectionTitle>
          Words{c.words.total ? ` · ${c.words.mastered} of ${c.words.total} mastered` : ""}
        </SectionTitle>
        {words.data?.map((w, i, all) => (
          <WordRow key={w.id} word={w} first={i === 0} last={i === all.length - 1} />
        ))}
        {words.data?.length === 0 && (
          <Text style={styles.muted}>No words linked to this chapter yet.</Text>
        )}
        <Button
          label="Add word"
          variant="secondary"
          onPress={() => router.push({ pathname: "/words/new", params: { chapterId: c.id } })}
        />

        <SectionTitle>Grammar</SectionTitle>
        {grammar.data?.map((p) => (
          <Card
            key={p.key}
            onPress={() => router.push({ pathname: "/grammar/[key]", params: { key: p.key } })}
            label={`${p.title}, ${percent(p.stats.accuracy)}`}
          >
            <View style={styles.grammarRow}>
              <Text style={styles.grammarTitle}>{p.title}</Text>
              <Text style={{ color: colors[LEVEL_COLORS[p.stats.level]], fontWeight: "800" }}>
                {percent(p.stats.accuracy)}
              </Text>
              <ChevronRight size={ICON.inline} color={colors.muted} />
            </View>
          </Card>
        ))}
        {grammar.data?.length === 0 && (
          <Text style={styles.muted}>
            No grammar linked yet. Open a rule in Grammar (in the ⋮ menu on Today) and tick this chapter.
          </Text>
        )}

        <Button
          label="Add resource"
          onPress={() =>
            router.push({ pathname: "/chapters/[id]/add-resource", params: { id: c.id } })
          }
        />
        <Button
          label="Edit chapter"
          variant="secondary"
          onPress={() => router.push({ pathname: "/chapters/[id]/edit", params: { id: c.id } })}
        />
        <Button
          label="Delete chapter"
          variant="danger"
          busy={deleteChapter.isPending}
          onPress={confirmDelete}
        />
      </FormScroll>
    </>
  );
}

function ResourceRow({ resource }: { resource: Resource }) {
  const colors = useTheme();
  const styles = useStyles();
  const update = useUpdateResource();
  const remove = useDeleteResource();
  const done = resource.completed_at !== null;

  // Secure links play inside the app, with the exercise and an answer box below. Anything else
  // (an http link) can only go to the phone's browser.
  function openLink() {
    if (!resource.url) return;
    if (canShowInApp(resource.url)) {
      router.push({
        pathname: "/player/[id]",
        params: { id: resource.id, chapterId: resource.chapter_id },
      });
    } else {
      Linking.openURL(resource.url).catch(() => Alert.alert("Couldn't open this link"));
    }
  }

  function confirmDelete() {
    Alert.alert("Delete this resource?", resource.title, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => remove.mutate(resource.id) },
    ]);
  }

  return (
    <Card>
      <View style={styles.resourceRow}>
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: done, disabled: update.isPending }}
          accessibilityLabel={done ? `Mark ${resource.title} as not done` : `Mark ${resource.title} as done`}
          onPress={() => update.mutate({ id: resource.id, completed: !done })}
          disabled={update.isPending}
          android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
          style={[styles.check, done && styles.checkDone]}
        >
          {done && <Check size={ICON.mark} strokeWidth={3} color={colors.onDone} />}
        </Pressable>
        <Pressable
          style={styles.resourceText}
          onLongPress={confirmDelete}
          accessibilityRole="text"
          accessibilityHint="Press and hold to delete"
          // The same action for a screen reader, which has no press-and-hold.
          accessibilityActions={[{ name: "delete", label: "Delete this resource" }]}
          onAccessibilityAction={(e) => e.nativeEvent.actionName === "delete" && confirmDelete()}
          android_ripple={{ color: colors.divider }}
        >
          <Text style={[styles.resourceTitle, done && styles.doneText]}>{resource.title}</Text>
          <Text style={styles.muted}>
            {kindLabel(resource.kind)}
            {resource.reference ? ` · ${resource.reference}` : ""}
          </Text>
        </Pressable>
        {resource.url && <TextLink label={canShowInApp(resource.url) ? "Play" : "Open"} onPress={openLink} />}
      </View>
      {update.isError && <ErrorText error={update.error} />}
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.md },
  title: { fontSize: 22, lineHeight: 30, fontWeight: "800" },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  body: { fontSize: 15, lineHeight: 22 },
  topics: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  topic: {
    backgroundColor: colors.well,
    borderRadius: 14,
    paddingHorizontal: 10,
    paddingVertical: 3,
    fontSize: 13,
    lineHeight: 18,
    overflow: "hidden",
  },
  resourceRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  grammarRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  grammarTitle: { flex: 1, fontSize: 16, lineHeight: 22, fontWeight: "600" },
  resourceText: { flex: 1, gap: 2, minHeight: TOUCH, justifyContent: "center" },
  resourceTitle: { fontSize: 16, lineHeight: 22, fontWeight: "600" },
  doneText: { color: colors.muted, textDecorationLine: "line-through" },
  check: {
    width: TOUCH,
    height: TOUCH,
    borderRadius: radius.md,
    backgroundColor: colors.well,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  checkDone: { backgroundColor: colors.done, borderColor: colors.done },
}));
