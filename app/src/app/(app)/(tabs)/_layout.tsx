import { Tabs } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppDrawer } from "@/features/navigation/AppDrawer";
import { MenuButton, StreakPill } from "@/features/navigation/TodayHeader";
import { AddWordButton } from "@/features/vocabulary/AddWordButton";
import { Backdrop, GlassFill } from "@/ui/glass";
import { BookA, BookOpen, ICON, MessagesSquare, PenLine, Sun, type Icon } from "@/ui/icons";
import { FONT_FAMILY, makeStyles, useTheme } from "@/ui/theme";

/** The tab's icon, in a pill when the tab is the open one (Material 3's navigation bar). */
function tabIcon(TabIcon: Icon) {
  function TabBarIcon({ focused }: { focused: boolean }) {
    const styles = useStyles();
    const colors = useTheme();
    return (
      <View style={[styles.pill, focused && styles.pillOn]}>
        <TabIcon size={ICON.bar} color={focused ? colors.onPrimaryContainer : colors.muted} />
      </View>
    );
  }
  return TabBarIcon;
}

const NAV_HEIGHT = 80;
const PILL = { width: 64, height: 32 } as const;

/**
 * Five daily tabs. Everything else (review, grammar, tools, account) is in the drawer, opened
 * by the ⋮ button on Today. The tab screens sit on the glass backdrop.
 */
export default function TabsLayout() {
  const colors = useTheme();
  const insets = useSafeAreaInsets();
  const [drawerOpen, setDrawerOpen] = useState(false);
  return (
    <Backdrop>
      <Tabs
        screenOptions={{
          sceneStyle: { backgroundColor: "transparent" },
          headerStyle: { backgroundColor: "transparent" },
          headerShadowVisible: false,
          headerTitleAlign: "left",
          headerTitleStyle: { fontFamily: FONT_FAMILY, fontSize: 22, fontWeight: "700", color: colors.text },
          tabBarActiveTintColor: colors.text,
          tabBarInactiveTintColor: colors.muted,
          // The icon slot is smaller than the active-tab pill by default (31x28): make room for it.
          tabBarIconStyle: { width: PILL.width, height: PILL.height },
          // The bar has a fixed height, so its 12dp labels stay at 12dp whatever the text size.
          tabBarAllowFontScaling: false,
          // The tab bar steps out of the way of the keyboard (the chat, the search box).
          tabBarHideOnKeyboard: true,
          tabBarLabelStyle: { fontFamily: FONT_FAMILY, fontSize: 12, fontWeight: "700", marginTop: 4 },
          tabBarStyle: {
            height: NAV_HEIGHT + insets.bottom,
            paddingTop: 12,
            backgroundColor: "transparent",
            borderTopWidth: 1,
            borderTopColor: colors.navBorder,
            elevation: 0,
          },
          tabBarBackground: () => <GlassFill color={colors.nav} />,
        }}
      >
        {/* The app opens at "/", so Today is the index route. */}
        <Tabs.Screen
          name="index"
          options={{
            title: "Today",
            tabBarIcon: tabIcon(Sun),
            headerLeft: () => <MenuButton onPress={() => setDrawerOpen(true)} />,
            headerRight: () => <StreakPill />,
          }}
        />
        <Tabs.Screen name="course" options={{ title: "Course", tabBarIcon: tabIcon(BookOpen) }} />
        <Tabs.Screen name="community" options={{ title: "Community", tabBarIcon: tabIcon(MessagesSquare) }} />
        <Tabs.Screen
          name="words"
          options={{ title: "Words", tabBarIcon: tabIcon(BookA), headerRight: () => <AddWordButton /> }}
        />
        <Tabs.Screen name="write" options={{ title: "Write", tabBarIcon: tabIcon(PenLine) }} />
      </Tabs>
      <AppDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </Backdrop>
  );
}

const useStyles = makeStyles((colors) => ({
  pill: { ...PILL, borderRadius: PILL.height / 2, alignItems: "center", justifyContent: "center" },
  pillOn: { backgroundColor: colors.primaryContainer },
}));
