import { Pressable, View } from "react-native";
import Animated from "react-native-reanimated";

import { ARTICLES } from "@/features/vocabulary/articleRules";
import type { Article } from "@/features/vocabulary/api";
import { Check, ICON, X } from "@/ui/icons";
import { usePop, useShake } from "@/ui/motion";
import { Text } from "@/ui/Text";
import { makeStyles, space, useTheme } from "@/ui/theme";

/**
 * How one button looks: `idle` is the tinted button, `selected` is picked but not yet checked,
 * `right` is the correct article once answered, `wrong` is the article that was picked instead.
 */
export type ButtonState = "idle" | "selected" | "right" | "wrong";

type Props = {
  state: (article: Article) => ButtonState;
  onPick: (article: Article) => void;
  label: string;
};

/**
 * der / die / das as three big buttons, tinted in the article's color (approved Words layout).
 * The article is always written out, and a right or wrong answer also gets a tick or a cross, so
 * color is never the only signal.
 */
export function ArticleButtons({ state, onPick, label }: Props) {
  const styles = useStyles();
  return (
    <View style={styles.row} accessibilityRole="radiogroup" accessibilityLabel={label}>
      {ARTICLES.map((article) => (
        <ArticleButton key={article} article={article} state={state(article)} onPick={onPick} />
      ))}
    </View>
  );
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

function ArticleButton({
  article,
  state,
  onPick,
}: {
  article: Article;
  state: ButtonState;
  onPick: (article: Article) => void;
}) {
  const styles = useStyles();
  const colors = useTheme();
  // The right answer pops; a wrong pick shakes. Both stay still with "Remove animations" on.
  const pop = usePop(state === "right");
  const shake = useShake(state === "wrong");
  const tone = colors[article];
  const ink = state === "right" ? tone.onFill : state === "wrong" ? colors.wrong.fg : tone.text;
  return (
    <AnimatedPressable
      accessibilityRole="radio"
      accessibilityLabel={article}
      accessibilityState={{ checked: state === "selected" || state === "right" || state === "wrong" }}
      onPress={() => onPick(article)}
      android_ripple={{ color: tone.fill + "33" }}
      style={[
        styles.button,
        { backgroundColor: tone.tint, borderColor: "transparent" },
        state === "selected" && { borderColor: tone.fill },
        state === "right" && { backgroundColor: tone.fill, borderColor: tone.fill },
        state === "wrong" && { backgroundColor: colors.wrong.bg, borderColor: colors.wrong.edge },
        pop,
        shake,
      ]}
    >
      {state === "right" && <Check size={ICON.inline} strokeWidth={3} color={ink} />}
      {state === "wrong" && <X size={ICON.badge} strokeWidth={3} color={ink} />}
      <Text style={[styles.text, { color: ink }]}>{article}</Text>
    </AnimatedPressable>
  );
}

const useStyles = makeStyles(() => ({
  row: { flexDirection: "row", gap: space.md },
  button: {
    flex: 1,
    minHeight: 64,
    borderRadius: 20,
    borderWidth: 2,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: space.sm,
    overflow: "hidden",
  },
  text: { fontSize: 22, lineHeight: 28, fontWeight: "800" },
}));
