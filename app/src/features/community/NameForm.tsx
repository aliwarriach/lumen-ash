import { useState } from "react";
import { View } from "react-native";

import { Text } from "@/ui/Text";
import { Button, ErrorText, Field } from "@/ui/components";
import { makeStyles, space } from "@/ui/theme";

import { useSetCommunityName } from "./api";
import { USERNAME_MAX, usernameProblem } from "./username";

/**
 * Chooses the username: the name other people see in the chat. It can be chosen once; after that
 * only a moderator can change it, so nobody can post something and then rename themselves.
 */
export function NameForm({ onDone, plain }: { onDone?: () => void; plain?: boolean }) {
  const styles = useStyles();
  const [name, setName] = useState("");
  const save = useSetCommunityName();
  const trimmed = name.trim();
  const problem = trimmed.length > 0 ? usernameProblem(trimmed) : null;
  const ready = trimmed.length > 0 && problem === null;

  return (
    <View style={plain ? styles.plain : styles.box}>
      <Text style={styles.title}>Choose your username</Text>
      <Text style={styles.hint}>
        Other people see this in the chat, never your email. Do not use your real name. It cannot
        be changed later, so choose carefully.
      </Text>
      <Field
        label="Username"
        value={name}
        onChangeText={setName}
        maxLength={USERNAME_MAX + 5}
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="username-new"
        returnKeyType="done"
        onSubmitEditing={() => ready && save.mutate(trimmed, { onSuccess: onDone })}
      />
      {problem && <ErrorText error={problem} />}
      {save.isError && <ErrorText error={save.error} />}
      <Button
        label="Save username"
        busy={save.isPending}
        disabled={!ready}
        onPress={() => save.mutate(trimmed, { onSuccess: onDone })}
      />
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  box: { gap: space.sm, padding: space.lg, backgroundColor: colors.surface },
  plain: { gap: space.sm },
  title: { fontSize: 16, fontWeight: "700", color: colors.text },
  hint: { color: colors.muted, fontSize: 13 },
}));
