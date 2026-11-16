import { router } from "expo-router";
import { Pressable, View } from "react-native";

import { CATEGORY_LABELS } from "@/features/grammar/api";
import type { Mistake } from "@/features/mistakes/api";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, useTheme, type Palette } from "@/ui/theme";

export function MistakeRow({ mistake }: { mistake: Mistake }) {
  const styles = useStyles();
  const colors = useTheme();
  const meta = [mistake.pattern_title ?? CATEGORY_LABELS[mistake.category], shortDate(mistake.created_at)];
  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => router.push({ pathname: "/mistakes/[id]", params: { id: mistake.id } })}
      android_ripple={{ color: colors.divider }}
      style={styles.row}
    >
      <Text style={styles.wrong}>{mistake.wrong}</Text>
      <Text style={styles.correct}>→ {mistake.correct}</Text>
      <View style={styles.metaRow}>
        <Text style={styles.meta} numberOfLines={1}>
          {meta.join(" · ")}
        </Text>
        {mistake.repeat_of && <Text style={styles.repeat}>Repeat</Text>}
      </View>
    </Pressable>
  );
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], { day: "numeric", month: "short" });
}

// What was wrong (struck through) and the correction, shared with the mistake and grammar screens.
const mistakeText = (colors: Palette) => ({
  wrong: {
    fontSize: 16,
    color: colors.danger,
    textDecorationLine: "line-through",
    textDecorationColor: colors.danger,
  },
  correct: { fontSize: 16, color: colors.success, fontWeight: "600" },
}) as const;

export const useMistakeStyles = makeStyles(mistakeText);

const useStyles = makeStyles((colors) => ({
  row: {
    backgroundColor: colors.flat,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: space.lg,
    gap: 2,
    overflow: "hidden",
  },
  ...mistakeText(colors),
  metaRow: { flexDirection: "row", alignItems: "center", gap: space.sm, marginTop: 2 },
  meta: { flex: 1, fontSize: 13, color: colors.muted },
  repeat: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.warning,
    borderWidth: 1,
    borderColor: colors.warning,
    borderRadius: radius.sm,
    paddingHorizontal: 6,
    overflow: "hidden",
  },
}));
