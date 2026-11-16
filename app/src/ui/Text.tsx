import { createContext, useContext, type ComponentPropsWithRef } from "react";
import { Text as RNText, TextInput as RNTextInput } from "react-native";

import { FONT_FAMILY, makeStyles, useTheme } from "@/ui/theme";

/**
 * The app's Text and TextInput: React Native's own, with the app font and the theme's text color
 * as the starting style. Without these, text with no color set stays black in dark mode.
 *
 * Text inside Text adds nothing, so it still inherits its parent's color and size, as in React
 * Native.
 */

const InsideText = createContext(false);

export function Text({ style, ...props }: ComponentPropsWithRef<typeof RNText>) {
  const styles = useStyles();
  const nested = useContext(InsideText);
  if (nested) return <RNText style={style} {...props} />;
  return (
    <InsideText.Provider value>
      <RNText style={[styles.text, style]} {...props} />
    </InsideText.Provider>
  );
}

export function TextInput({ style, ...props }: ComponentPropsWithRef<typeof RNTextInput>) {
  const styles = useStyles();
  const colors = useTheme();
  return (
    <RNTextInput
      placeholderTextColor={colors.muted}
      selectionColor={colors.primary}
      cursorColor={colors.primary}
      style={[styles.text, style]}
      {...props}
    />
  );
}

const useStyles = makeStyles((colors) => ({
  text: { fontFamily: FONT_FAMILY, color: colors.text },
}));
