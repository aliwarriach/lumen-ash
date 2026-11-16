import type { ReactNode } from "react";
import { KeyboardAvoidingView, ScrollView } from "react-native";

import { Text } from "@/ui/Text";
import { Backdrop, Glass } from "@/ui/glass";
import { makeStyles, space } from "@/ui/theme";

/**
 * The page the screens before sign-in share: the colored backdrop, a title, and one glass card.
 * These screens have no header, so there is no height to allow for; "padding" because the window
 * no longer shrinks for the keyboard on Android (see ui/FormScroll.tsx).
 */
export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const styles = useStyles();
  return (
    <Backdrop>
      <KeyboardAvoidingView style={styles.screen} behavior="padding">
        <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
          <Text style={styles.title} accessibilityRole="header">
            {title}
          </Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          <Glass style={styles.card}>{children}</Glass>
        </ScrollView>
      </KeyboardAvoidingView>
    </Backdrop>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1 },
  form: { flexGrow: 1, justifyContent: "center", padding: space.xl, gap: space.md },
  card: { gap: space.lg },
  title: { fontSize: 30, lineHeight: 38, fontWeight: "800" },
  subtitle: { fontSize: 16, lineHeight: 24, color: colors.muted, marginBottom: space.sm },
}));
