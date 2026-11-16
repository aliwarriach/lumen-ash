import { router } from "expo-router";
import { useState } from "react";

import { AuthShell } from "@/features/auth/AuthShell";
import { looksLikeEmail, passwordProblem } from "@/features/auth/password";
import { supabase } from "@/lib/supabase";
import { Text } from "@/ui/Text";
import { Button, ErrorText, Field, TextLink } from "@/ui/components";
import { makeStyles } from "@/ui/theme";

// Open sign-up: anyone can make an account, but must confirm their email before the first sign-in.
// The username is chosen on the first sign-in (see features/account/UsernameGate.tsx).
export default function SignUp() {
  const styles = useStyles();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  const problem = passwordProblem(password, again);
  const ready = looksLikeEmail(email) && problem === null;

  async function signUp() {
    setBusy(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signUp({ email: email.trim(), password });
      if (authError) setError(authError.message);
      else setSentTo(email.trim());
    } catch {
      setError("Can't reach the sign-up service. Check your internet connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  if (sentTo) {
    return (
      <AuthShell title="Check your email">
        <Text style={styles.body}>
          We sent a confirmation link to {sentTo}. Open it, then come back here and sign in. If
          nothing arrives within a few minutes, look in your spam folder.
        </Text>
        <Button label="Go to sign in" onPress={() => router.replace("/sign-in")} />
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create your account" subtitle="Free. You confirm your email first.">
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
        label="Password (at least 8 characters)"
        autoCapitalize="none"
        autoComplete="new-password"
        secureTextEntry
        returnKeyType="next"
        value={password}
        onChangeText={setPassword}
      />
      <Field
        label="Password again"
        autoCapitalize="none"
        autoComplete="new-password"
        secureTextEntry
        returnKeyType="go"
        onSubmitEditing={() => ready && !busy && void signUp()}
        value={again}
        onChangeText={setAgain}
      />
      {again.length > 0 && problem ? <ErrorText error={problem} /> : null}
      {error && <ErrorText error={error} />}
      <Button label="Create account" busy={busy} disabled={!ready} onPress={() => void signUp()} />
      <TextLink label="I already have an account" onPress={() => router.replace("/sign-in")} />
    </AuthShell>
  );
}

const useStyles = makeStyles((colors) => ({
  body: { fontSize: 16, lineHeight: 24, color: colors.text },
}));
