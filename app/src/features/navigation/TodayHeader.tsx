import { Pressable, View } from "react-native";

import { useDashboard } from "@/features/dashboard/api";
import { EllipsisVertical, Flame, ICON } from "@/ui/icons";
import { Text } from "@/ui/Text";
import { makeStyles, space, TOUCH, useTheme } from "@/ui/theme";

/** The ⋮ button at the top left of Today: opens the drawer. */
export function MenuButton({ onPress }: { onPress: () => void }) {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Menu"
      accessibilityHint="Review, grammar, tools and account"
      onPress={onPress}
      android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
      style={styles.menu}
    >
      <EllipsisVertical size={ICON.bar} color={colors.text} />
    </Pressable>
  );
}

/** The amber day-streak pill at the top right of Today. Hidden until the plan has loaded. */
export function StreakPill() {
  const styles = useStyles();
  const colors = useTheme();
  const streak = useDashboard().data?.on_track.streak;
  if (streak === undefined) return null;
  return (
    <View
      style={styles.pill}
      accessible
      accessibilityLabel={`${streak} day streak`}
    >
      <Flame size={ICON.badge} color={colors.amber.fg} />
      <Text style={styles.pillText}>{streak}</Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  menu: {
    width: TOUCH,
    height: TOUCH,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: space.xs,
  },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
    minHeight: 36,
    paddingHorizontal: space.md,
    borderRadius: 18,
    backgroundColor: colors.amber.bg,
    marginRight: space.lg,
  },
  pillText: { fontSize: 15, lineHeight: 20, fontWeight: "800", color: colors.amber.fg },
}));
