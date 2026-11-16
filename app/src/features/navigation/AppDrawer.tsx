import { router, type Href } from "expo-router";
import { useEffect, useState } from "react";
import { Animated, Easing, Modal, Pressable, ScrollView, Switch, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  CircleUserRound,
  ClipboardList,
  ICON,
  Moon,
  Repeat2,
  ScanText,
  SpellCheck,
  type Icon,
} from "@/ui/icons";
import { DURATION, useReduceMotion } from "@/ui/motion";
import { Text } from "@/ui/Text";
import { makeStyles, space, TOUCH, useTheme } from "@/ui/theme";
import { useThemePreference } from "@/ui/ThemeProvider";

type Item = { label: string; icon: Icon; href: Href };

/** What lives in the drawer: everything that is not a daily tab. */
const GROUPS: { title: string; items: Item[] }[] = [
  {
    title: "Study",
    items: [
      { label: "Review", icon: Repeat2, href: "/review" },
      { label: "Grammar", icon: SpellCheck, href: "/grammar" },
    ],
  },
  {
    title: "Tools",
    items: [
      { label: "Scan an exercise from a book", icon: ScanText, href: "/scanner" },
      { label: "Class tasks from WhatsApp", icon: ClipboardList, href: "/capture" },
    ],
  },
];

const ACCOUNT: Item = { label: "Account and daily reminder", icon: CircleUserRound, href: "/account" };

/**
 * The left drawer, opened by the ⋮ button on Today (Reddit's pattern). It slides in over a scrim;
 * a tap on the scrim, the back button or any row closes it. With "Remove animations" on, it
 * simply appears.
 */
export function AppDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const styles = useStyles();
  const colors = useTheme();
  const insets = useSafeAreaInsets();
  const { width: screen } = useWindowDimensions();
  const width = Math.min(320, Math.round(screen * 0.85));
  const reduceMotion = useReduceMotion();
  const { preference, setPreference } = useThemePreference();

  // Mount as soon as it opens; stay mounted while sliding out, then unmount.
  const [mounted, setMounted] = useState(open);
  if (open && !mounted) setMounted(true);
  const [progress] = useState(() => new Animated.Value(0));
  useEffect(() => {
    // With "Remove animations" on, a zero-length animation: it still ends, and unmounts, the same way.
    Animated.timing(progress, {
      toValue: open ? 1 : 0,
      duration: reduceMotion ? 0 : DURATION.medium,
      easing: open ? Easing.out(Easing.cubic) : Easing.in(Easing.cubic),
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished && !open) setMounted(false);
    });
  }, [open, reduceMotion, progress]);

  const go = (href: Href) => {
    onClose();
    router.push(href);
  };

  const dark = colors.scheme === "dark";
  const translateX = progress.interpolate({ inputRange: [0, 1], outputRange: [-width, 0] });

  return (
    <Modal visible={mounted || open} transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
      <Animated.View style={[styles.scrim, { opacity: progress }]}>
        <Pressable style={styles.fill} onPress={onClose} accessibilityLabel="Close menu" />
      </Animated.View>
      <Animated.View
        style={[styles.panel, { width, paddingTop: insets.top + space.lg, transform: [{ translateX }] }]}
        accessibilityViewIsModal
      >
        <ScrollView contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + space.lg }]}>
          <Text style={styles.appName} accessibilityRole="header">
            Lumen A1
          </Text>
          {GROUPS.map((g) => (
            <View key={g.title} style={styles.group}>
              <Text style={styles.groupTitle}>{g.title.toUpperCase()}</Text>
              {g.items.map((item) => (
                <Row key={item.label} item={item} onPress={() => go(item.href)} />
              ))}
            </View>
          ))}

          <View style={styles.footer}>
            <Row item={ACCOUNT} onPress={() => go(ACCOUNT.href)} />
            <View style={styles.row}>
              <Moon size={ICON.bar} color={colors.muted} />
              <Text style={styles.rowLabel} nativeID="dark-mode-label">
                Dark mode
              </Text>
              <Switch
                value={dark}
                onValueChange={(on) => setPreference(on ? "dark" : "light")}
                accessibilityLabelledBy="dark-mode-label"
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={dark ? colors.onPrimary : colors.background}
              />
            </View>
            {preference === "system" ? (
              <Text style={styles.note}>Follows your phone&apos;s setting until you change it.</Text>
            ) : (
              <Pressable
                accessibilityRole="button"
                onPress={() => setPreference("system")}
                style={styles.linkButton}
                android_ripple={{ color: colors.divider }}
              >
                <Text style={styles.link}>Follow my phone&apos;s setting</Text>
              </Pressable>
            )}
          </View>
        </ScrollView>
      </Animated.View>
    </Modal>
  );
}

function Row({ item, onPress }: { item: Item; onPress: () => void }) {
  const styles = useStyles();
  const colors = useTheme();
  const RowIcon = item.icon;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      android_ripple={{ color: colors.divider }}
      style={styles.row}
    >
      <RowIcon size={ICON.bar} color={colors.muted} />
      <Text style={styles.rowLabel}>{item.label}</Text>
    </Pressable>
  );
}

const useStyles = makeStyles((colors) => ({
  fill: { flex: 1 },
  scrim: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, backgroundColor: colors.scrim },
  panel: {
    position: "absolute",
    top: 0,
    bottom: 0,
    left: 0,
    backgroundColor: colors.sheet,
    borderTopRightRadius: 28,
    borderBottomRightRadius: 28,
    borderRightWidth: 1,
    borderColor: colors.cardBorder,
    boxShadow: `0 8px 32px ${colors.shadow}`,
  },
  content: { paddingHorizontal: space.md, gap: space.lg },
  appName: { fontSize: 22, lineHeight: 30, fontWeight: "800", paddingHorizontal: space.md },
  group: { gap: 2 },
  groupTitle: {
    fontSize: 13,
    lineHeight: 18,
    fontWeight: "700",
    letterSpacing: 0.8,
    color: colors.muted,
    paddingHorizontal: space.md,
    paddingBottom: space.xs,
  },
  row: {
    minHeight: TOUCH + 8,
    flexDirection: "row",
    alignItems: "center",
    gap: space.lg,
    paddingHorizontal: space.md,
    borderRadius: 28,
    overflow: "hidden",
  },
  rowLabel: { flex: 1, fontSize: 16, lineHeight: 22, fontWeight: "600" },
  footer: {
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingTop: space.md,
    gap: 2,
  },
  note: { fontSize: 13, lineHeight: 18, color: colors.muted, paddingHorizontal: space.md },
  linkButton: {
    minHeight: TOUCH,
    justifyContent: "center",
    paddingHorizontal: space.md,
    borderRadius: 24,
    overflow: "hidden",
  },
  link: { fontSize: 15, lineHeight: 20, fontWeight: "700", color: colors.primary },
}));
