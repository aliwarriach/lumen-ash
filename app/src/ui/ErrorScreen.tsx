import type { ErrorBoundaryProps } from "expo-router";
import { View } from "react-native";

import { Text } from "@/ui/Text";
import { Button } from "@/ui/components";
import { makeStyles, space } from "@/ui/theme";

/**
 * What the learner sees if a screen crashes: a plain page with a way out, not a blank screen.
 * Exported as `ErrorBoundary` from the root and app layouts, which is how Expo Router finds it.
 */
export function AppErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  const styles = useStyles();
  return (
    <View style={styles.page}>
      <Text style={styles.title}>Something went wrong</Text>
      <Text style={styles.body}>
        Your answers and words are safe. Try again; if it keeps happening, close the app and open
        it again.
      </Text>
      <Text style={styles.detail}>{error.message}</Text>
      <Button label="Try again" onPress={() => void retry()} />
    </View>
  );
}

/**
 * Shown instead of the app when the build is missing a setting (see lib/env-check.ts). The
 * learner can't fix this; the text is for whoever built the app.
 */
export function ConfigProblemScreen({ problems }: { problems: readonly string[] }) {
  const styles = useStyles();
  return (
    <View style={styles.page}>
      <Text style={styles.title} accessibilityRole="header">
        This copy of the app isn&apos;t set up
      </Text>
      <Text style={styles.body}>
        It was built without the settings it needs, so it can&apos;t sign in or reach the server.
        Your data is not affected. Please ask whoever gave you the app for a new copy.
      </Text>
      {problems.map((p) => (
        <Text key={p} style={styles.detail}>
          • {p}
        </Text>
      ))}
      <Text style={styles.detail}>
        For the builder: set these in app/.env (development) or in EAS for the build profile
        (release). See docs/INSTALL.md.
      </Text>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  page: {
    flex: 1,
    justifyContent: "center",
    padding: space.xl,
    gap: space.lg,
    backgroundColor: colors.background,
  },
  title: { fontSize: 22, fontWeight: "700", color: colors.text },
  body: { fontSize: 16, color: colors.text },
  detail: { fontSize: 13, color: colors.muted },
}));
