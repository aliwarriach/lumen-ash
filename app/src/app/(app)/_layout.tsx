import { Stack, router, usePathname } from "expo-router";
import { useShareIntentContext } from "expo-share-intent";
import { useEffect } from "react";
import { StyleSheet, View } from "react-native";

import { useWarmServer } from "@/api/warm";
import { UsernameGate } from "@/features/account/UsernameGate";
import { useCommunityMe } from "@/features/community/api";
import { useTaskReminderSync } from "@/features/capture/reminders";
import { Backdrop } from "@/ui/glass";
import { FONT_FAMILY, useTheme } from "@/ui/theme";

export { AppErrorBoundary as ErrorBoundary } from "@/ui/ErrorScreen";

const MAX_SHARED_CHARS = 6000;

export default function AppLayout() {
  const colors = useTheme();
  const { hasShareIntent, shareIntent, resetShareIntent } = useShareIntentContext();
  const pathname = usePathname();
  // Keep the phone's task reminders in step with the saved tasks, whichever screen is open.
  useTaskReminderSync();
  // Wake the free server now, while the learner is still reading the Today screen.
  useWarmServer();
  // Everyone needs a username. Only a loaded answer of "none yet" blocks the app: if the check
  // fails (offline), the person still gets in, because review and Today work offline.
  const me = useCommunityMe();

  // Something was shared to the app (a WhatsApp message): open the capture screen with it. `n`
  // changes every time, so a second share while the screen is open still reaches it.
  useEffect(() => {
    if (!hasShareIntent) return;
    const text = (shareIntent.text ?? shareIntent.webUrl ?? "").trim().slice(0, MAX_SHARED_CHARS);
    const params = { text, image: !text && shareIntent.files?.length ? "1" : "", n: String(Date.now()) };
    if (pathname === "/capture/new") router.setParams(params);
    else router.push({ pathname: "/capture/new", params });
    resetShareIntent();
  }, [hasShareIntent, shareIntent, pathname, resetShareIntent]);

  const needsUsername = me.data !== undefined && me.data.display_name === null;

  return (
    <View style={{ flex: 1 }}>
    <Stack
      // Every screen opened on top of the tabs gets the colored backdrop. It is opaque and moves with
      // its screen, so the slide transition does not show two pages through each other. The tabs
      // (a screen of this stack too) draw their own.
      screenLayout={({ route, children }) =>
        route.name === "(tabs)" ? children : <Backdrop>{children}</Backdrop>
      }
      screenOptions={{
        contentStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTitleStyle: { fontFamily: FONT_FAMILY, fontSize: 20, fontWeight: "700", color: colors.text },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="account" options={{ title: "Account and reminder" }} />
      <Stack.Screen name="chapters/new" options={{ title: "New chapter", presentation: "modal" }} />
      <Stack.Screen name="chapters/[id]/index" options={{ title: "Chapter" }} />
      <Stack.Screen
        name="chapters/[id]/edit"
        options={{ title: "Edit chapter", presentation: "modal" }}
      />
      <Stack.Screen
        name="chapters/[id]/add-resource"
        options={{ title: "Add resource", presentation: "modal" }}
      />
      <Stack.Screen name="review/index" options={{ title: "Review" }} />
      <Stack.Screen
        name="review/session"
        options={{ title: "Review", presentation: "fullScreenModal" }}
      />
      <Stack.Screen name="words/new" options={{ title: "Add word", presentation: "modal" }} />
      <Stack.Screen name="words/[id]/index" options={{ title: "Word" }} />
      <Stack.Screen name="words/[id]/edit" options={{ title: "Edit word", presentation: "modal" }} />
      <Stack.Screen name="exams/index" options={{ title: "Tests" }} />
      <Stack.Screen name="exams/new" options={{ title: "Add a test", presentation: "modal" }} />
      <Stack.Screen name="exams/[id]" options={{ title: "Test" }} />
      <Stack.Screen name="exams/result" options={{ title: "Add a result", presentation: "modal" }} />
      <Stack.Screen name="capture/index" options={{ title: "Class tasks" }} />
      <Stack.Screen
        name="capture/new"
        options={{ title: "Add from a message", presentation: "modal" }}
      />
      <Stack.Screen name="player/[id]" options={{ title: "Resource" }} />
      <Stack.Screen name="scanner/index" options={{ title: "Scan an exercise" }} />
      <Stack.Screen name="grammar/index" options={{ title: "Grammar" }} />
      <Stack.Screen name="grammar/[key]" options={{ title: "Grammar" }} />
      <Stack.Screen name="grammar/practice/[key]" options={{ title: "Practice" }} />
      <Stack.Screen name="sentences/[id]" options={{ title: "Sentences" }} />
      <Stack.Screen name="mistakes/index" options={{ title: "Mistake log" }} />
      <Stack.Screen name="mistakes/new" options={{ title: "Log a mistake", presentation: "modal" }} />
      <Stack.Screen name="mistakes/[id]/index" options={{ title: "Mistake" }} />
      <Stack.Screen
        name="mistakes/[id]/edit"
        options={{ title: "Edit mistake", presentation: "modal" }}
      />
    </Stack>
    {/* Drawn over the app, which stays mounted underneath: a layout must keep its navigator. */}
    {needsUsername && (
      <View style={StyleSheet.absoluteFill}>
        <UsernameGate />
      </View>
    )}
    </View>
  );
}
