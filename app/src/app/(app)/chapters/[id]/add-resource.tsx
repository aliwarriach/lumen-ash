import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, View } from "react-native";

import { RESOURCE_KINDS, useCreateResource, type ResourceKind } from "@/features/course/api";
import { Button, ErrorText, Field } from "@/ui/components";
import { FormScroll } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

export default function AddResource() {
  const styles = useStyles();
  const colors = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const create = useCreateResource(id);
  const [kind, setKind] = useState<ResourceKind>("book_page");
  const [title, setTitle] = useState("");
  const [reference, setReference] = useState("");
  const [url, setUrl] = useState("");

  const trimmedUrl = url.trim();
  const urlOk = trimmedUrl === "" || /^https?:\/\/\S+$/i.test(trimmedUrl);

  return (
    <FormScroll contentContainerStyle={styles.form}>
      <View style={styles.kinds}>
        {RESOURCE_KINDS.map((k) => (
          <Pressable
            key={k.kind}
            accessibilityRole="radio"
            accessibilityState={{ selected: kind === k.kind }}
            onPress={() => setKind(k.kind)}
            android_ripple={{ color: colors.divider }}
            style={[styles.kind, kind === k.kind && styles.kindSelected]}
          >
            <Text style={[styles.kindText, kind === k.kind && styles.kindTextSelected]}>
              {k.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <Field label="Title" value={title} onChangeText={setTitle} placeholder="e.g. Hörtext 2" />
      <Field
        label="Where in the book (optional)"
        value={reference}
        onChangeText={setReference}
        placeholder="e.g. S. 24, Ü 3"
      />
      <Field
        label="Allango or other link (optional)"
        value={url}
        onChangeText={setUrl}
        autoCapitalize="none"
        keyboardType="url"
        placeholder="https://"
      />
      {!urlOk && <Text accessibilityLiveRegion="polite" style={styles.error}>Links must start with http:// or https://</Text>}
      {create.error != null && <ErrorText error={create.error} />}
      <Button
        label="Add"
        busy={create.isPending}
        disabled={!title.trim() || !urlOk}
        onPress={() =>
          create.mutate(
            {
              kind,
              title: title.trim(),
              reference: reference.trim() || null,
              url: trimmedUrl || null,
            },
            { onSuccess: () => router.back() },
          )
        }
      />
    </FormScroll>
  );
}

const useStyles = makeStyles((colors) => ({
  form: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl, gap: space.lg },
  kinds: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  kind: {
    minHeight: TOUCH,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space.lg,
    overflow: "hidden",
  },
  kindSelected: { backgroundColor: colors.primaryContainer, borderColor: colors.primaryContainer },
  kindText: { fontSize: 15, lineHeight: 22 },
  kindTextSelected: { color: colors.onPrimaryContainer, fontWeight: "700" },
  error: { color: colors.danger },
}));
