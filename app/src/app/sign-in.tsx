import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, ScrollView } from "react-native";

import { supabase } from "@/lib/supabase";
import { Text } from "@/ui/Text";
import { Button, ErrorText, Field, TextLink } from "@/ui/components";
import { Backdrop, Glass } from "@/ui/glass";
import { makeStyles, space } from "@/ui/theme";

// Anyone can create an account (sign-up) after confirming their email.
export default function SignIn() {
  const styles = useStyles();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signIn() {
    setBusy(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (authError) setError(authError.message);
    } catch {
      setError("Can't reach the sign-in service. Check your internet connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    // This screen has no header, so there is no height to allow for. "padding" because the window
    // no longer shrinks for the keyboard on Android (see ui/FormScroll.tsx).
    <Backdrop>
    <KeyboardAvoidingView style={styles.screen} behavior="padding">
      <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
        <Text style={styles.title} accessibilityRole="header">
          Lumen A1
        </Text>
        <Text style={styles.subtitle}>Your German study companion</Text>
        <Glass style={styles.card}>
        <Field
          label="Email"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          keyboardType="email-address"
          returnKeyType="next"
          value={email}
          onChangeText={setEmail}
        />
        <Field
          label="Password"
          autoCapitalize="none"
          autoComplete="current-password"
          secureTextEntry
          returnKeyType="go"
          onSubmitEditing={() => email && password && !busy && void signIn()}
          value={password}
          onChangeText={setPassword}
        />
        {error && <ErrorText error={error} />}
        <Button label="Sign in" busy={busy} disabled={!email || !password} onPress={() => void signIn()} />
        <TextLink label="Forgot your password?" onPress={() => router.push("/forgot-password")} />
        <TextLink label="Create an account" onPress={() => router.push("/sign-up")} />
        </Glass>
      </ScrollView>
    </KeyboardAvoidingView>
    </Backdrop>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1 },
  form: { flexGrow: 1, justifyContent: "center", padding: space.xl, gap: space.md },
  card: { gap: space.lg },
  title: { fontSize: 34, lineHeight: 42, fontWeight: "800" },
  subtitle: { fontSize: 16, lineHeight: 24, color: colors.muted, marginBottom: space.lg },
}));
