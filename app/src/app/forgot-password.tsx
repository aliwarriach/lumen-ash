import { router } from "expo-router";
import { useState } from "react";

import { AuthShell } from "@/features/auth/AuthShell";
import { looksLikeEmail, passwordProblem } from "@/features/auth/password";
import { supabase } from "@/lib/supabase";
import { Text } from "@/ui/Text";
import { Button, ErrorText, Field, TextLink } from "@/ui/components";
import { makeStyles } from "@/ui/theme";

// Two steps, no links to open: we email a code, the person types it here with a new password. A
// link would have to open the app from the email and survive other phones and email apps; a code
// works anywhere. (The "Reset Password" email in Supabase must contain {{ .Token }}: see README.)
export default function ForgotPassword() {
  const styles = useStyles();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function sendCode() {
    setBusy(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.resetPasswordForEmail(email.trim());
      if (authError) setError(authError.message);
      else setSent(true);
    } catch {
      setError("Can't reach the service. Check your internet connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function setNewPassword() {
    setBusy(true);
    setError(null);
    try {
      const { error: codeError } = await supabase.auth.verifyOtp({
        email: email.trim(),
        token: code.trim(),
        type: "recovery",
      });
      if (codeError) {
        setError("That code didn't work. Check it, or ask for a new one (codes expire after an hour).");
        return;
      }
      // The code signs the person in, and the app then leaves this screen on its own. The new
      // password is saved straight away, while that happens.
      const { error: passwordError } = await supabase.auth.updateUser({ password });
      if (passwordError) setError(passwordError.message);
    } catch {
      setError("Can't reach the service. Check your internet connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!sent) {
    return (
      <AuthShell title="Forgot your password?" subtitle="We'll email you a code.">
        <Field
          label="Email"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          keyboardType="email-address"
          returnKeyType="go"
          onSubmitEditing={() => looksLikeEmail(email) && !busy && void sendCode()}
          value={email}
          onChangeText={setEmail}
        />
        {error && <ErrorText error={error} />}
        <Button label="Send code" busy={busy} disabled={!looksLikeEmail(email)} onPress={() => void sendCode()} />
        <TextLink label="Back to sign in" onPress={() => router.replace("/sign-in")} />
      </AuthShell>
    );
  }

  const problem = passwordProblem(password, again);
  const ready = code.trim().length >= 6 && problem === null;
  return (
    <AuthShell title="Enter the code">
      <Text style={styles.body}>
        If {email.trim()} has an account, we sent it a code.
      </Text>
      <Field
        label="Code from the email"
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="one-time-code"
        keyboardType="number-pad"
        returnKeyType="next"
        value={code}
        onChangeText={setCode}
      />
      <Text style={styles.spam}>No email? Check your Spam or Junk folder. The code can take a minute.</Text>
      <Field
        label="New password (at least 8 characters)"
        autoCapitalize="none"
        autoComplete="new-password"
        secureTextEntry
        returnKeyType="next"
        value={password}
        onChangeText={setPassword}
      />
      <Field
        label="New password again"
        autoCapitalize="none"
        autoComplete="new-password"
        secureTextEntry
        returnKeyType="go"
        onSubmitEditing={() => ready && !busy && void setNewPassword()}
        value={again}
        onChangeText={setAgain}
      />
      {again.length > 0 && problem ? <ErrorText error={problem} /> : null}
      {error && <ErrorText error={error} />}
      <Button label="Save new password" busy={busy} disabled={!ready} onPress={() => void setNewPassword()} />
      <TextLink label="Send a new code" onPress={() => void sendCode()} />
      <TextLink label="Back to sign in" onPress={() => router.replace("/sign-in")} />
    </AuthShell>
  );
}

const useStyles = makeStyles((colors) => ({
  body: { fontSize: 15, lineHeight: 22, color: colors.muted },
  spam: { fontSize: 14, lineHeight: 20, fontWeight: "700", color: colors.text },
}));
