import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, View } from "react-native";

import { remainingText, useAiQuota } from "@/features/ai/api";
import {
  KIND_LABELS,
  useCreateTasks,
  useScanMessage,
  type ClassTaskInput,
  type ProposedTask,
  type TaskKind,
} from "@/features/capture/api";
import {
  CHOICE_LABELS,
  defaultChoice,
  describeReminder,
  ensureNotificationPermission,
  reminderTime,
  type ReminderChoice,
} from "@/features/capture/reminders";
import { isValidIsoDate, isoDate } from "@/features/exams/api";
import { Button, Card, Chips, ErrorText, Field } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Check, ICON } from "@/ui/icons";
import { Text, TextInput } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

const MAX_TASKS = 10;
const IMAGE_NOTE =
  "Screenshots can't be read yet. In WhatsApp, press and hold the message, tap Copy, then paste it here.";

type Draft = {
  key: string;
  include: boolean;
  kind: TaskKind;
  title: string;
  due: string; // YYYY-MM-DD, or "" for no date
  dueText: string | null; // the words the date came from
  url: string | null;
  remind: ReminderChoice | null; // null = pick automatically from the date
  duplicate: boolean;
};

let nextKey = 0;
function newDraft(partial: Partial<Draft> = {}): Draft {
  return {
    key: String(nextKey++),
    include: true,
    kind: "homework",
    title: "",
    due: "",
    dueText: null,
    url: null,
    remind: null,
    duplicate: false,
    ...partial,
  };
}

function fromProposed(p: ProposedTask): Draft {
  return newDraft({
    include: !p.duplicate, // a task you already saved is left unticked
    kind: p.kind,
    title: p.title,
    due: p.due_date ?? "",
    dueText: p.due_text,
    url: p.url,
    duplicate: p.duplicate,
  });
}

function shortLink(link: string): string {
  const bare = link.replace(/^https?:\/\//i, "").replace(/^www\./i, "");
  return bare.length > 30 ? `${bare.slice(0, 29)}…` : bare;
}

const KINDS = (Object.keys(KIND_LABELS) as TaskKind[]).map((k) => ({
  value: k,
  label: KIND_LABELS[k],
}));
const CHOICES = (Object.keys(CHOICE_LABELS) as ReminderChoice[]).map((c) => ({
  value: c,
  label: CHOICE_LABELS[c],
}));
const QUICK_DATES = [
  { value: "today", label: "Today" },
  { value: "tomorrow", label: "Tomorrow" },
  { value: "week", label: "In a week" },
  { value: "none", label: "No date" },
];

export default function CaptureNew() {
  const styles = useStyles();
  const colors = useTheme();
  const scan = useScanMessage();
  const create = useCreateTasks();
  const quota = useAiQuota();
  // A message shared from WhatsApp (or any app) arrives as params, put there by the app layout.
  const shared = useLocalSearchParams<{ text?: string; image?: string; n?: string }>();

  const [stage, setStage] = useState<"message" | "review">("message");
  // The message is copied into the box, so the learner sees exactly what will be sent and can
  // remove anything they'd rather not share.
  const [text, setText] = useState(shared.text ?? "");
  const [note, setNote] = useState<string | null>(shared.image ? IMAGE_NOTE : null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [links, setLinks] = useState<string[]>([]);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Shared again while this screen is open: start over with the new message. (State is adjusted
  // while rendering, as React recommends for "reset when a prop changes".)
  const [seen, setSeen] = useState(shared.n);
  if (seen !== shared.n) {
    setSeen(shared.n);
    setText(shared.text ?? "");
    setNote(shared.image ? IMAGE_NOTE : null);
    setStage("message");
  }

  const scansLeft = quota.data?.features.find((f) => f.feature === "message_capture");

  function find() {
    scan.mutate(text.trim(), {
      onSuccess: (result) => {
        setDrafts(result.items.map(fromProposed));
        setLinks(result.links);
        setNote(result.message);
        setSaveError(null);
        setStage("review");
      },
    });
  }

  function byHand() {
    setDrafts([newDraft()]);
    setLinks([]);
    setNote(null);
    setSaveError(null);
    setStage("review");
  }

  function change(key: string, changes: Partial<Draft>) {
    setDrafts((all) => all.map((d) => (d.key === key ? { ...d, ...changes } : d)));
  }

  const chosen = drafts.filter((d) => d.include);
  const problem = chosen.some((d) => !d.title.trim())
    ? "Every task needs a title."
    : chosen.some((d) => d.due !== "" && !isValidIsoDate(d.due))
      ? "Write dates like 2026-12-15, or choose No date."
      : null;

  async function save() {
    const items: ClassTaskInput[] = chosen.map((d) => {
      const due = d.due === "" ? null : d.due;
      const at = reminderTime(d.remind ?? defaultChoice(due), due);
      return {
        kind: d.kind,
        title: d.title.trim(),
        due_date: due,
        due_text: d.dueText,
        url: d.url,
        remind_at: at ? at.toISOString() : null,
      };
    });
    if (items.some((i) => i.remind_at)) {
      // Ask now, while the learner knows why. If they say no the tasks are still saved, and the
      // task list explains that reminders are blocked.
      await ensureNotificationPermission().catch(() => false);
    }
    create.mutate(items, {
      onSuccess: () => router.replace("/capture"),
      onError: (e) => setSaveError(e instanceof Error ? e.message : "Could not save."),
    });
  }

  if (stage === "message") {
    return (
      <FormScroll contentContainerStyle={styles.page}>
        <Text style={styles.help}>
          In WhatsApp, press and hold a message from your class chat, tap Copy, and paste it here.
          If your WhatsApp offers Share for the message, you can share it straight to Lumen A1
          instead. You check the tasks before anything is saved.
        </Text>
        <TextInput
          style={styles.message}
          multiline
          textAlignVertical="top"
          value={text}
          onChangeText={setText}
          placeholder="Paste the message here"
          placeholderTextColor={colors.muted}
          accessibilityLabel="Message from your class chat"
        />
        {note && <Text accessibilityLiveRegion="polite" style={styles.warning}>{note}</Text>}
        <Text style={styles.small}>
          Phone numbers, emails and links are removed before the text goes to the AI. Names in the
          text may not be, so delete any you’d rather not send.
        </Text>
        {scansLeft && <Text style={styles.small}>{remainingText(scansLeft)}</Text>}
        {scan.isError && (
          <>
            <ErrorText error={scan.error} />
            <Text style={styles.small}>You can still add the task by hand.</Text>
          </>
        )}
        <Button
          label="Find tasks"
          busy={scan.isPending}
          disabled={text.trim().length === 0 || scansLeft?.remaining === 0}
          onPress={find}
        />
        <Button label="Add a task by hand" variant="secondary" onPress={byHand} />
      </FormScroll>
    );
  }

  return (
    <FormScroll contentContainerStyle={styles.page}>
      <Text style={styles.help}>
        {drafts.length === 0
          ? "Nothing to save yet."
          : "Check each task, fix anything that's wrong, and save the ones you want. Nothing is saved until you do."}
      </Text>
      {note && <Text accessibilityLiveRegion="polite" style={styles.warning}>{note}</Text>}
      {drafts.map((d) => (
        <DraftCard key={d.key} draft={d} links={links} onChange={(c) => change(d.key, c)} />
      ))}
      {drafts.length < MAX_TASKS && (
        <Button
          label="Add another task"
          variant="secondary"
          onPress={() => setDrafts((all) => [...all, newDraft()])}
        />
      )}
      {problem && chosen.length > 0 && <Text accessibilityLiveRegion="polite" style={styles.warning}>{problem}</Text>}
      {saveError && <ErrorText error={new Error(saveError)} />}
      <Button
        label={chosen.length === 1 ? "Save 1 task" : `Save ${chosen.length} tasks`}
        busy={create.isPending}
        disabled={chosen.length === 0 || problem !== null}
        onPress={() => void save()}
      />
      <Button label="Back to the message" variant="secondary" onPress={() => setStage("message")} />
    </FormScroll>
  );
}

function DraftCard({
  draft,
  links,
  onChange,
}: {
  draft: Draft;
  links: string[];
  onChange: (changes: Partial<Draft>) => void;
}) {
  const colors = useTheme();
  const styles = useStyles();
  const dueValid = draft.due === "" || isValidIsoDate(draft.due);
  const due = draft.due === "" ? null : dueValid ? draft.due : null;
  const choice = draft.remind ?? defaultChoice(due);
  const at = reminderTime(choice, due);
  const quick =
    draft.due === ""
      ? "none"
      : draft.due === isoDate(0)
        ? "today"
        : draft.due === isoDate(1)
          ? "tomorrow"
          : draft.due === isoDate(7)
            ? "week"
            : null;

  return (
    <Card>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: draft.include }}
        onPress={() => onChange({ include: !draft.include })}
        android_ripple={{ color: colors.divider }}
        style={styles.includeRow}
      >
        <View style={[styles.box, draft.include && styles.boxOn]}>
          {draft.include && <Check size={ICON.mark} strokeWidth={3} color={colors.onDone} />}
        </View>
        <Text style={styles.includeText}>
          {draft.include ? "Save this task" : "Not saving this task"}
          {draft.duplicate ? " (you already have it)" : ""}
        </Text>
      </Pressable>
      {draft.include && (
        <>
          <Field
            label="Task"
            value={draft.title}
            onChangeText={(title) => onChange({ title })}
            placeholder="Workbook page 24"
            maxLength={200}
          />
          <Chips
            label="What is it?"
            options={KINDS}
            selected={draft.kind}
            onSelect={(kind) => onChange({ kind })}
          />
          <Field
            label={
              draft.dueText && dueValid
                ? `Due date (from "${draft.dueText}")`
                : "Due date (year-month-day)"
            }
            value={draft.due}
            onChangeText={(value) => onChange({ due: value.trim(), dueText: null })}
            placeholder="2026-12-15"
            autoCapitalize="none"
            keyboardType="numbers-and-punctuation"
          />
          <Chips
            options={QUICK_DATES}
            selected={quick}
            onSelect={(q) =>
              onChange({
                due: q === "today" ? isoDate(0) : q === "tomorrow" ? isoDate(1) : q === "week" ? isoDate(7) : "",
                dueText: null,
              })
            }
          />
          {draft.due !== "" && !dueValid && (
            <Text style={styles.warning}>Write the date like 2026-12-15.</Text>
          )}
          {due !== null && due < isoDate(0) && (
            <Text style={styles.warning}>This date has already passed. Is it right?</Text>
          )}
          {draft.due === "" && (
            <Text style={styles.small}>With no date there is no reminder and it stays out of today’s plan.</Text>
          )}
          {links.length > 0 && (
            <Chips
              label="Link"
              options={[
                { value: "", label: "No link" },
                ...links.map((l) => ({ value: l, label: shortLink(l) })),
              ]}
              selected={draft.url ?? ""}
              onSelect={(url) => onChange({ url: url === "" ? null : url })}
            />
          )}
          <Chips
            label="Remind me"
            options={CHOICES}
            selected={choice}
            onSelect={(remind) => onChange({ remind })}
          />
          <Text style={styles.small}>
            {at
              ? `Reminder: ${describeReminder(at)}`
              : choice !== "none"
                ? "That time has already passed, so there won't be a reminder."
                : due === null
                  ? "Add a date to get a reminder."
                  : "No reminder."}
          </Text>
        </>
      )}
    </Card>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  help: { fontSize: 15, lineHeight: 22, color: colors.muted },
  small: { fontSize: 14, lineHeight: 20, color: colors.muted },
  warning: { fontSize: 14, lineHeight: 20, fontWeight: "600", color: colors.warning },
  message: {
    minHeight: 180,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: radius.md,
    padding: space.lg,
    fontSize: 16,
    color: colors.text,
  },
  includeRow: { flexDirection: "row", alignItems: "center", gap: space.md, minHeight: TOUCH },
  includeText: { flex: 1, fontSize: 15, lineHeight: 22, fontWeight: "700", color: colors.text },
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
  boxOn: { backgroundColor: colors.done, borderColor: colors.done },
}));
