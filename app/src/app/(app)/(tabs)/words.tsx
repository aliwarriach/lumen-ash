import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, FlatList, View } from "react-native";

import { ArticleFilterChips, ArticleKey, ArticleQuiz } from "@/features/vocabulary/ArticleQuiz";
import { WordRow } from "@/features/vocabulary/WordRow";
import { filterByArticle, quizNouns, type ArticleFilter } from "@/features/vocabulary/articleRules";
import { useWords } from "@/features/vocabulary/api";
import { useDebounced } from "@/lib/useDebounced";
import { Button, Card, Centered, ErrorText, Field } from "@/ui/components";
import { AvoidKeyboard } from "@/ui/FormScroll";
import { Text } from "@/ui/Text";
import { makeStyles, space } from "@/ui/theme";

/**
 * Words, as approved for the glass restyle: the "Which article?" quiz in glass, the colour key,
 * a search box, the All / der / die / das filter, and the words in one rounded list.
 */
export default function Words() {
  const styles = useStyles();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<ArticleFilter>("all");
  const q = useDebounced(search.trim());
  const words = useWords({ q });
  // The quiz asks about every noun, whatever is typed in the search box.
  const all = useWords({});
  const pool = quizNouns(all.data ?? []);
  const shown = filterByArticle(words.data ?? [], filter);

  const header = (
    <View style={styles.header}>
      {pool.length > 0 && <ArticleQuiz pool={pool} />}
      <ArticleKey />
      <Field
        label=""
        value={search}
        onChangeText={setSearch}
        placeholder="Search your words"
        accessibilityLabel="Search your words"
        autoCapitalize="none"
        returnKeyType="search"
      />
      <ArticleFilterChips value={filter} onChange={setFilter} />
    </View>
  );

  return (
    <AvoidKeyboard>
      {words.isPending ? (
        <Centered>
          <ActivityIndicator />
        </Centered>
      ) : words.isError ? (
        <Centered>
          <ErrorText error={words.error} />
        </Centered>
      ) : (
        <FlatList
          data={shown}
          keyExtractor={(w) => w.id}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.list}
          ListHeaderComponent={header}
          renderItem={({ item, index }) => (
            <WordRow word={item} first={index === 0} last={index === shown.length - 1} />
          )}
          ListEmptyComponent={
            <Card>
              <Text style={styles.muted}>
                {q || filter !== "all"
                  ? "No saved words match."
                  : "No words yet. Add words from class: the dictionary fills in articles, plurals and verb forms for you."}
              </Text>
              {!q && filter === "all" && (
                <Button label="Add word" onPress={() => router.push("/words/new")} />
              )}
            </Card>
          }
        />
      )}
    </AvoidKeyboard>
  );
}

const useStyles = makeStyles((colors) => ({
  header: { gap: space.xl - 4, paddingBottom: space.lg },
  list: { paddingHorizontal: space.lg, paddingTop: space.xs, paddingBottom: space.xl },
  muted: { color: colors.muted },
}));
