import { router } from "expo-router";
import { Pressable, View } from "react-native";

import { kindLabel } from "@/features/vocabulary/articleRules";
import { headword, type Word } from "@/features/vocabulary/api";
import { Text } from "@/ui/Text";
import { makeStyles, radius, space, useTheme } from "@/ui/theme";

type Props = {
  word: Word;
  /** Rows are drawn as one rounded list: the first and last row round its ends. */
  first?: boolean;
  last?: boolean;
};

/**
 * One word in the list: its article in the article's color (or its word type, for words with no
 * article), the word and its meaning, and the plural in grey. Opens the word.
 */
export function WordRow({ word, first = false, last = false }: Props) {
  const styles = useStyles();
  const colors = useTheme();
  const plural = word.plural_only ? "plural only" : word.plural ? `die ${word.plural}` : null;
  const label = [headword(word), word.meaning_en, plural].filter(Boolean).join(", ");
  return (
    <View style={[styles.outer, first && styles.first, last && styles.last]}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityHint="Opens the word"
        onPress={() => router.push({ pathname: "/words/[id]", params: { id: word.id } })}
        android_ripple={{ color: colors.divider }}
        style={[styles.row, !first && styles.divider]}
      >
        {word.article ? (
          <Text style={[styles.article, { color: colors[word.article].text }]}>{word.article}</Text>
        ) : (
          <Text style={styles.kind}>{kindLabel(word.kind)}</Text>
        )}
        <View style={styles.text}>
          <Text style={styles.german}>{word.german}</Text>
          <Text style={styles.meaning} numberOfLines={1}>
            {word.meaning_en}
          </Text>
        </View>
        {plural && <Text style={styles.plural}>{plural}</Text>}
      </Pressable>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  outer: {
    backgroundColor: colors.card,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: colors.cardBorder,
    overflow: "hidden",
  },
  first: { borderTopWidth: 1, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg },
  last: { borderBottomWidth: 1, borderBottomLeftRadius: radius.lg, borderBottomRightRadius: radius.lg },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    minHeight: 56,
    paddingVertical: space.md,
    paddingHorizontal: space.lg,
  },
  divider: { borderTopWidth: 1, borderTopColor: colors.divider },
  article: { width: 44, fontSize: 16, lineHeight: 22, fontWeight: "800" },
  kind: { width: 44, fontSize: 13, lineHeight: 18, fontWeight: "700", color: colors.muted },
  text: { flex: 1, minWidth: 0 },
  german: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  meaning: { fontSize: 14, lineHeight: 20, color: colors.muted },
  plural: { fontSize: 14, lineHeight: 20, color: colors.plural, textAlign: "right" },
}));
