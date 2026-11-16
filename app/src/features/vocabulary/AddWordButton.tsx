import { router } from "expo-router";
import { Pressable } from "react-native";

import { ICON, Plus } from "@/ui/icons";
import { makeStyles, space, TOUCH, useTheme } from "@/ui/theme";

/** The + at the top right of the Words tab: opens the add-word form. */
export function AddWordButton() {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Add word"
      onPress={() => router.push("/words/new")}
      android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
      style={styles.button}
    >
      <Plus size={ICON.bar} color={colors.text} />
    </Pressable>
  );
}

const useStyles = makeStyles(() => ({
  button: {
    width: TOUCH,
    height: TOUCH,
    alignItems: "center",
    justifyContent: "center",
    marginRight: space.sm,
  },
}));
