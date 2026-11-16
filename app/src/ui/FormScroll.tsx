import { useSegments } from "expo-router";
import { HeaderHeightContext } from "expo-router/react-navigation";
import { useContext } from "react";
import {
  KeyboardAvoidingView,
  ScrollView,
  StyleSheet,
  View,
  type KeyboardAvoidingViewProps,
  type ScrollViewProps,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useKeyboardOpen } from "@/ui/useKeyboardOpen";

/**
 * Keeps what is inside it above the keyboard.
 *
 * Expo apps on Android draw edge to edge, so the window no longer shrinks when the keyboard
 * opens: without this, the keyboard simply covers the lower part of the screen, input included
 * (https://docs.expo.dev/guides/keyboard-handling/). The view measures itself from the top of its
 * screen, which starts below the header, so the header's height is passed as the offset. A tab bar
 * below needs nothing: the view already ends above it.
 */
export function AvoidKeyboard({ style, ...props }: KeyboardAvoidingViewProps) {
  // Screens without a header (none use this today) have no height to add.
  const headerHeight = useContext(HeaderHeightContext) ?? 0;
  return (
    <KeyboardAvoidingView
      behavior="padding"
      keyboardVerticalOffset={headerHeight}
      style={[styles.fill, style]}
      {...props}
    />
  );
}

/**
 * The scrolling page for any screen with a text input. When the keyboard opens, the page shrinks
 * to the space above it, so the field being typed in and the button under it can be scrolled to.
 * A tap on a button while the keyboard is open presses the button instead of only closing the
 * keyboard.
 *
 * Also keeps the last button off Android's navigation bar. Screens draw edge to edge, so on a
 * screen without a tab bar the bottom of the page would sit under that bar. A tab screen needs
 * nothing (the tab bar already covers that strip), and neither does a screen with the keyboard
 * open (the keyboard covers it, and adding the height again would leave a gap above the keyboard).
 */
export function FormScroll(props: ScrollViewProps) {
  const insets = useSafeAreaInsets();
  // The tab screens live in the "(tabs)" group of the route.
  const inTabs = (useSegments() as string[]).includes("(tabs)");
  const keyboardOpen = useKeyboardOpen();
  return (
    <View style={[styles.fill, { paddingBottom: inTabs || keyboardOpen ? 0 : insets.bottom }]}>
      <AvoidKeyboard>
        <ScrollView keyboardShouldPersistTaps="handled" {...props} />
      </AvoidKeyboard>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
});

/**
 * The space to leave at the bottom of a scrolling list that is not a FormScroll (a FlatList), so its
 * last row is not under Android's navigation bar. Zero on a tab screen and with the keyboard open,
 * for the reasons given on FormScroll.
 */
export function useBottomInset(): number {
  const insets = useSafeAreaInsets();
  const inTabs = (useSegments() as string[]).includes("(tabs)");
  const keyboardOpen = useKeyboardOpen();
  return inTabs || keyboardOpen ? 0 : insets.bottom;
}
