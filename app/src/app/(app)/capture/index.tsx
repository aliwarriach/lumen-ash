import * as Notifications from "expo-notifications";
import { router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Alert, Linking, Pressable, RefreshControl, View } from "react-native";

import {
  KIND_LABELS,
  dueLabel,
  useClassTasks,
  useDeleteTask,
  useUpdateTask,
  type ClassTask,
} from "@/features/capture/api";
import { describeReminder } from "@/features/capture/reminders";
import { Check, ICON } from "@/ui/icons";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, Loading, SectionTitle, TextLink } from "@/ui/components";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

export default function ClassTasks() {
  const styles = useStyles();
  const tasks = useClassTasks(true);
  const update = useUpdateTask();
  const remove = useDeleteTask();
  const blocked = useRemindersBlocked(tasks.data);

  if (!tasks.data) {
    return (
      <Centered>
        {tasks.isError ? <ErrorText error={tasks.error} /> : <Loading />}
      </Centered>
    );
  }

  const open = tasks.data.filter((t) => !t.done);
  const done = tasks.data.filter((t) => t.done);

  function confirmDelete(task: ClassTask) {
    Alert.alert("Delete this task?", task.title, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => remove.mutate(task.id) },
    ]);
  }

  return (
    <FormScroll
      contentContainerStyle={styles.page}
      refreshControl={
        <RefreshControl refreshing={tasks.isRefetching} onRefresh={() => void tasks.refetch()} />
      }
    >
      <Button label="Add from a message" onPress={() => router.push("/capture/new")} />
      {blocked && (
        <Text style={styles.warning}>
          Reminders can’t show: notifications are turned off for this app. Allow them in Android
          settings.
        </Text>
      )}
      {(update.isError || remove.isError) && <ErrorText error={update.error ?? remove.error} />}

      {open.length === 0 ? (
        <Text style={styles.muted}>
          No open tasks. Share a message from your class chat to add some.
        </Text>
      ) : (
        open.map((t, i) => (
          <TaskRow
            key={t.id}
            // The first open task is the one glass card.
            glass={i === 0}
            task={t}
            onToggle={() => update.mutate({ id: t.id, changes: { done: true } })}
            onDelete={() => confirmDelete(t)}
          />
        ))
      )}

      {done.length > 0 && (
        <View style={styles.section}>
          <SectionTitle>Finished in the last 2 weeks</SectionTitle>
          {done.map((t) => (
            <TaskRow
              key={t.id}
              task={t}
              onToggle={() => update.mutate({ id: t.id, changes: { done: false } })}
              onDelete={() => confirmDelete(t)}
            />
          ))}
        </View>
      )}
    </FormScroll>
  );
}

function TaskRow({
  task,
  glass = false,
  onToggle,
  onDelete,
}: {
  task: ClassTask;
  glass?: boolean;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const colors = useTheme();
  const styles = useStyles();
  const overdue = !task.done && task.days_left !== null && task.days_left < 0;
  return (
    <Card glass={glass}>
      <View style={styles.row}>
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: task.done }}
          accessibilityLabel={task.done ? `Mark "${task.title}" as not done` : `Mark "${task.title}" as done`}
          onPress={onToggle}
          android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
          style={[styles.box, task.done && styles.boxDone]}
        >
          {task.done && <Check size={ICON.mark} strokeWidth={3} color={colors.onDone} />}
        </Pressable>
        <View style={styles.text}>
          <Text style={[styles.title, task.done && styles.doneText]}>{task.title}</Text>
          <Text style={[styles.muted, overdue && styles.overdue]}>
            {KIND_LABELS[task.kind]} · {dueLabel(task)}
          </Text>
          {!task.done && task.remind_at && (
            <Text style={styles.muted}>Reminder: {describeReminder(new Date(task.remind_at))}</Text>
          )}
          <View style={styles.actions}>
            {task.url && (
              <TextLink label="Open the link" onPress={() => void Linking.openURL(task.url as string)} />
            )}
            <TextLink label="Delete" tone="danger" onPress={onDelete} />
          </View>
        </View>
      </View>
    </Card>
  );
}

/** True when some open task wants a reminder but Android isn't letting this app show one. */
function useRemindersBlocked(tasks: ClassTask[] | undefined): boolean {
  const wanted = (tasks ?? []).some((t) => !t.done && t.remind_at);
  const permission = useQuery({
    queryKey: ["notification-permission"],
    queryFn: async () => (await Notifications.getPermissionsAsync()).status !== "granted",
    enabled: wanted,
    staleTime: 0,
  });
  return wanted && permission.data === true;
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  section: { gap: space.md - 2 },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
  warning: { fontSize: 14, lineHeight: 20, fontWeight: "600", color: colors.warning },
  overdue: { color: colors.danger, fontWeight: "700" },
  row: { flexDirection: "row", gap: space.md, alignItems: "flex-start" },
  text: { flex: 1, gap: 2 },
  actions: { flexDirection: "row", gap: space.lg },
  title: { fontSize: 16, lineHeight: 22, fontWeight: "700" },
  doneText: { textDecorationLine: "line-through", color: colors.muted },
  box: {
    width: TOUCH,
    height: TOUCH,
    borderRadius: radius.md,
    backgroundColor: colors.well,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  boxDone: { backgroundColor: colors.done, borderColor: colors.done },
}));
