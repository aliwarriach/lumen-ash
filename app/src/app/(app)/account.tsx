import { useQuery } from "@tanstack/react-query";
import { View } from "react-native";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import { remainingText, useAiQuota } from "@/features/ai/api";
import { flushOutbox } from "@/features/review/outbox";
import { formatTime, useReminder } from "@/features/reminders/reminder";
import { supabase } from "@/lib/supabase";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { Button, Card, Chips, ErrorText } from "@/ui/components";
import { makeStyles, space } from "@/ui/theme";

const REMINDER_HOURS = [7, 12, 18, 20, 21];

export default function Account() {
  const styles = useStyles();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => unwrap(await api.GET("/me")),
  });
  const db = useQuery({
    queryKey: ["health", "db"],
    queryFn: async () => unwrap(await api.GET("/health/db")),
  });

  const ai = useAiQuota();
  const reminder = useReminder();

  return (
    <FormScroll contentContainerStyle={styles.page}>
      <Card glass>
        <Row label="Signed in as" value={me.data?.email ?? (me.isPending ? "…" : "Unknown")} />
        <Row
          label="Server"
          value={db.isPending ? "Checking…" : db.isSuccess ? "Connected" : "Unreachable"}
        />
      </Card>
      <Card>
        <Text style={styles.heading}>AI help today</Text>
        {ai.isPending ? (
          <Text style={styles.value}>…</Text>
        ) : ai.isError ? (
          <Text style={styles.label}>Could not check. Reviews and words still work.</Text>
        ) : !ai.data.available ? (
          <Text style={styles.label}>AI help is not available right now. Everything else works.</Text>
        ) : (
          ai.data.features.map((f) => (
            <Text key={f.feature} style={styles.value}>
              {remainingText(f)}
            </Text>
          ))
        )}
      </Card>
      <Card>
        <Text style={styles.heading}>Daily reminder</Text>
        <Text style={styles.value}>
          {reminder.reminder.enabled
            ? `Every day at ${formatTime(reminder.reminder.hour, reminder.reminder.minute)}`
            : "Off"}
        </Text>
        <Chips
          label="Remind me at"
          selected={reminder.reminder.enabled ? String(reminder.reminder.hour) : null}
          onSelect={(hour) => void reminder.enable(Number(hour), 0)}
          options={REMINDER_HOURS.map((h) => ({ value: String(h), label: formatTime(h, 0) }))}
        />
        {reminder.reminder.enabled && (
          <Button
            label="Turn reminder off"
            variant="secondary"
            busy={reminder.busy}
            onPress={() => void reminder.disable()}
          />
        )}
        {reminder.error && <ErrorText error={new Error(reminder.error)} />}
      </Card>
      <Button
        label="Sign out"
        variant="secondary"
        onPress={async () => {
          await flushOutbox(); // upload answers saved on the phone before they're cleared
          await supabase.auth.signOut();
        }}
      />
    </FormScroll>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const styles = useStyles();
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  page: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  row: { gap: 2 },
  heading: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  label: { fontSize: 14, lineHeight: 20, color: colors.muted },
  value: { fontSize: 16, lineHeight: 24, fontWeight: "600" },
}));
