import { Stack, router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useRef, useState, type ComponentType, type Ref } from "react";
import { ActivityIndicator, Animated, BackHandler, Keyboard, Linking, PanResponder, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { WebView as PackagedWebView, type WebViewNavigation } from "react-native-webview";
import type { AndroidWebViewProps } from "react-native-webview/lib/WebViewTypes";

import { useCheckWriting, type CheckResult, type Correction } from "@/features/coach/api";
import { CheckResultView } from "@/features/coach/CheckResultView";
import { AskCommunityButton } from "@/features/community/AskCommunity";
import { aboutResource } from "@/features/community/ask";
import { kindLabel, useChapter, useUpdateResource } from "@/features/course/api";
import { canShowInApp, decide, describeHttpError } from "@/features/player/policy";
import { ChevronDown, ChevronLeft, ChevronUp, ExternalLink, ICON, RotateCw } from "@/ui/icons";
import { useReduceMotion } from "@/ui/motion";
import { Text } from "@/ui/Text";
import { Button, Card, Centered, ErrorText, Field, IconLabel } from "@/ui/components";
import { makeStyles, radius, space, TOUCH, useTheme } from "@/ui/theme";

// The package types its props as iOS & Android & Windows at once, which no value satisfies. This
// app is Android only, so type it with the Android props.
const WebView = PackagedWebView as unknown as ComponentType<
  AndroidWebViewProps & { ref?: Ref<{ goBack(): void; reload(): void }> }
>;

// The bottom bar that is always visible: a grab handle and the page controls.
const HANDLE_HEIGHT = TOUCH;
const ACTIONS_HEIGHT = TOUCH;
// How tall the opened sheet is, as a share of the screen. The page stays full size underneath.
const SHEET_SHARE = 0.72;

// Development only: reports what the page does when audio fails (failed requests, refused
// playback, pop-ups) to the Metro log on the computer. Query strings are cut off so no token or
// signed address is ever written down. Nothing is sent anywhere, and release builds don't include it.
const DIAGNOSTIC = `(function () {
  function send(o) { try { window.ReactNativeWebView.postMessage(JSON.stringify(o)); } catch (e) {} }
  function clean(u) { try { var x = new URL(u, location.href); return x.origin + x.pathname; } catch (e) { return String(u).slice(0, 120); } }
  var f = window.fetch;
  if (f) window.fetch = function (i, o) {
    var u = clean(typeof i === 'string' ? i : (i && i.url));
    return f.apply(this, arguments).then(function (r) { if (!r.ok) send({ t: 'fetch', s: r.status, u: u }); return r; },
      function (e) { send({ t: 'fetch-failed', u: u, m: String(e) }); throw e; });
  };
  var xo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u) {
    var c = clean(u);
    this.addEventListener('loadend', function () { if (this.status === 0 || this.status >= 400) send({ t: 'xhr', s: this.status, u: c }); });
    return xo.apply(this, arguments);
  };
  var pl = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    var p = pl.apply(this, arguments);
    if (p && p.catch) p.catch(function (e) { send({ t: 'play-refused', m: e.name + ': ' + e.message }); });
    return p;
  };
  window.addEventListener('error', function (e) {
    var t = e.target;
    if (t && (t.tagName === 'AUDIO' || t.tagName === 'VIDEO' || t.tagName === 'SOURCE')) send({ t: 'media-error', u: clean(t.currentSrc || t.src), code: t.error && t.error.code });
    else send({ t: 'js-error', m: String(e.message).slice(0, 200) });
  }, true);
  window.addEventListener('unhandledrejection', function (e) { send({ t: 'rejection', m: String((e.reason && e.reason.message) || e.reason).slice(0, 200) }); });
  var wo = window.open;
  window.open = function (u) { send({ t: 'window.open', u: clean(u) }); return wo.apply(this, arguments); };
  send({ t: 'start', ua: navigator.userAgent });
})(); true;`;

// Opens one chapter resource (an Allango audio or video, an exercise page) INSIDE the app. The page
// takes the whole screen above a slim bar; the bar pulls up into a sheet with the exercise, the
// done tick and an answer box. Only the link is stored; the page is Allango's own player.
export default function Player() {
  const styles = useStyles();
  const colors = useTheme();
  const { id, chapterId } = useLocalSearchParams<{ id: string; chapterId: string }>();
  const chapter = useChapter(chapterId);
  const resource = chapter.data?.resources.find((r) => r.id === id);

  if (chapter.isPending) {
    return (
      <Centered>
        <ActivityIndicator color={colors.primary} />
      </Centered>
    );
  }
  if (chapter.isError) {
    return (
      <Centered>
        <ErrorText error={chapter.error} />
        <Button label="Try again" variant="secondary" onPress={() => chapter.refetch()} />
      </Centered>
    );
  }
  if (!resource) {
    return (
      <Centered>
        <Text style={styles.muted}>This resource no longer exists.</Text>
        <Button label="Back" variant="secondary" onPress={() => router.back()} />
      </Centered>
    );
  }
  return <Page resource={resource} chapterNumber={chapter.data?.number ?? null} />;
}

function openInBrowser(url: string) {
  Linking.openURL(url).catch(() => undefined);
}

/** Height of the on-screen keyboard, 0 when it is closed. */
function useKeyboardHeight(): number {
  const [height, setHeight] = useState(Keyboard.isVisible() ? Keyboard.metrics()?.height ?? 0 : 0);
  useEffect(() => {
    const show = Keyboard.addListener("keyboardDidShow", (e) => setHeight(e.endCoordinates.height));
    const hide = Keyboard.addListener("keyboardDidHide", () => setHeight(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);
  return height;
}

function Page({
  resource,
  chapterNumber,
}: {
  resource: NonNullable<ReturnType<typeof useChapter>["data"]>["resources"][number];
  chapterNumber: number | null;
}) {
  const colors = useTheme();
  const styles = useStyles();
  const link = resource.url;
  const web = useRef<{ goBack(): void; reload(): void }>(null);
  const [canGoBack, setCanGoBack] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const update = useUpdateResource();
  const done = resource.completed_at !== null;

  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const check = useCheckWriting();
  function decided(c: Correction) {
    setResult((r) => r && { ...r, corrections: r.corrections.map((x) => (x.id === c.id ? c : x)) });
  }

  function onNavigation(nav: WebViewNavigation) {
    setCanGoBack(nav.canGoBack);
  }

  // --- The bottom sheet ---
  const insets = useSafeAreaInsets();
  const keyboard = useKeyboardHeight();
  const [screenHeight, setScreenHeight] = useState(0);
  const [expanded, setExpanded] = useState(false);

  // Edge to edge: the window does not shrink for the keyboard, and the navigation bar is drawn
  // over the bottom of the screen. So the bar keeps clear of the navigation bar, and the opened
  // sheet lifts above the keyboard.
  const peek = HANDLE_HEIGHT + ACTIONS_HEIGHT + insets.bottom;
  const sheetHeight = Math.max(
    peek + 160,
    Math.min(screenHeight * SHEET_SHARE, screenHeight - keyboard - space.lg),
  );
  const closedOffset = sheetHeight - peek;

  const [offset] = useState(() => new Animated.Value(0));
  // With Android's "Remove animations" on, the sheet jumps instead of sliding.
  const reduceMotion = useReduceMotion();
  const current = useRef(0);
  useEffect(() => {
    const id = offset.addListener(({ value }) => {
      current.current = value;
    });
    return () => offset.removeListener(id);
  }, [offset]);

  function settle(open: boolean) {
    setExpanded(open);
    Animated.timing(offset, {
      toValue: open ? 0 : closedOffset,
      duration: reduceMotion ? 0 : 220,
      useNativeDriver: false,
    }).start();
  }
  // Keep the sheet where it belongs when the screen is measured or the keyboard comes and goes.
  useEffect(() => {
    offset.setValue(expanded ? 0 : closedOffset);
    // Only the size changing should move it: opening and closing go through settle().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [closedOffset]);
  // Typing needs the sheet open: the keyboard opening opens it, and it stays open afterwards.
  useEffect(() => {
    const sub = Keyboard.addListener("keyboardDidShow", () => settle(true));
    return () => sub.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [closedOffset]);
  // The back button closes the sheet before it leaves the screen.
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!expanded) return false;
      Keyboard.dismiss();
      settle(false);
      return true;
    });
    return () => sub.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, closedOffset]);

  // Dragging the handle moves the sheet; letting go snaps it open or closed.
  const dragFrom = useRef(0);
  // The handlers below read refs only when a finger moves, never while rendering.
  /* eslint-disable react-hooks/refs */
  const pan = useMemo(
    () =>
      PanResponder.create({
        // Only a vertical drag takes over: a plain tap still reaches the buttons.
        onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dy) > 6 && Math.abs(g.dy) > Math.abs(g.dx),
        onPanResponderGrant: () => {
          offset.stopAnimation();
          dragFrom.current = current.current;
        },
        onPanResponderMove: (_e, g) => {
          offset.setValue(Math.min(Math.max(dragFrom.current + g.dy, 0), closedOffset));
        },
        onPanResponderRelease: (_e, g) => {
          const open = g.vy < -0.4 ? true : g.vy > 0.4 ? false : current.current < closedOffset / 2;
          if (!open) Keyboard.dismiss();
          settle(open);
        },
      }),
    // settle() reads closedOffset, so a new size needs a new responder.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [closedOffset],
  );
  /* eslint-enable react-hooks/refs */

  const showsPage = canShowInApp(link);

  return (
    <View style={styles.screen} onLayout={(e) => setScreenHeight(e.nativeEvent.layout.height)}>
      <Stack.Screen options={{ title: resource.title }} />

      {/* The page: everything above the bar. The sheet slides over it without resizing it, so
          the audio keeps playing and the page doesn't reload. */}
      <View style={[styles.player, { bottom: peek }]}>
        {showsPage ? (
          <>
            <WebView
              ref={web}
              source={{ uri: link ?? undefined }}
              style={styles.web}
              // Allango's own player is a web app: it needs scripts and storage. The view isn't
              // private (that is Android's default), so its sign-in is remembered between visits.
              javaScriptEnabled
              domStorageEnabled
              thirdPartyCookiesEnabled
              // Allango fetches the audio address after the tap and starts playing afterwards.
              // With Android's default the view then refuses ("needs a tap"), and the player
              // loads for ever. This allows playback the page starts itself.
              mediaPlaybackRequiresUserAction={false}
              injectedJavaScriptBeforeContentLoaded={__DEV__ ? DIAGNOSTIC : undefined}
              onMessage={(e) => {
                if (__DEV__) console.log("[allango]", e.nativeEvent.data);
              }}
              // Never the phone's files, and no pop-up windows: links open in this view and are
              // checked below like every other navigation.
              allowFileAccess={false}
              setSupportMultipleWindows={false}
              // The policy decides everything, so let every address reach it (the default would
              // hand unlisted ones such as intent: links straight to Android).
              originWhitelist={["*"]}
              onShouldStartLoadWithRequest={(req) => {
                const verdict = decide(req.url, link);
                if (__DEV__) console.log("[allango] nav", verdict, req.url.split(/[?#]/)[0]);
                if (verdict === "external") openInBrowser(req.url);
                return verdict === "allow";
              }}
              onNavigationStateChange={onNavigation}
              onLoadStart={() => {
                setLoading(true);
                setProblem(null);
              }}
              onLoadEnd={() => setLoading(false)}
              onHttpError={(e) => setProblem(describeHttpError(e.nativeEvent.statusCode))}
              onError={() =>
                setProblem("The page couldn't load. Check your internet connection, or open it in your browser.")
              }
            />
            {loading && !problem && (
              <View pointerEvents="none" style={styles.loading}>
                <ActivityIndicator color={colors.primary} />
              </View>
            )}
            {problem && (
              <Text accessibilityLiveRegion="polite" style={styles.problem}>
                {problem}
              </Text>
            )}
          </>
        ) : (
          <Centered>
            <Text style={styles.muted}>
              {link
                ? "This link isn't a secure (https) web link, so it opens in your browser."
                : "This resource has no link yet."}
            </Text>
          </Centered>
        )}
      </View>

      <Animated.View
        style={[
          styles.sheet,
          { height: sheetHeight, bottom: keyboard, transform: [{ translateY: offset }] },
        ]}
      >
        {/* The part that is always showing: handle, then the page controls. */}
        <View {...pan.panHandlers}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={expanded ? "Close the exercise sheet" : "Open the exercise sheet"}
            accessibilityState={{ expanded }}
            onPress={() => {
              if (expanded) Keyboard.dismiss();
              settle(!expanded);
            }}
            android_ripple={{ color: colors.divider }}
            style={styles.handleArea}
          >
            <View style={styles.grabber} />
            <IconLabel trailing icon={expanded ? ChevronDown : ChevronUp} color={colors.muted} style={styles.handleLabel}>
              Exercise & answer
            </IconLabel>
          </Pressable>
          <View style={styles.actions}>
            {showsPage && (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Back in the page"
                accessibilityState={{ disabled: !canGoBack }}
                disabled={!canGoBack}
                onPress={() => web.current?.goBack()}
                android_ripple={{ color: colors.divider }}
                style={styles.actionTarget}
              >
                <ChevronLeft size={ICON.inline} color={canGoBack ? colors.primary : colors.muted} />
                <Text style={[styles.action, !canGoBack && styles.actionOff]}>Back</Text>
              </Pressable>
            )}
            {showsPage && (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Reload the page"
                onPress={() => web.current?.reload()}
                android_ripple={{ color: colors.divider, borderless: true, radius: TOUCH / 2 }}
                style={styles.iconTarget}
              >
                <RotateCw size={ICON.inline} color={colors.primary} />
              </Pressable>
            )}
            <AskCommunityButton
              iconOnly
              about={resource.title}
              attachment={() =>
                aboutResource(resource, kindLabel(resource.kind), chapterNumber, answer.trim() || null)
              }
            />
            {link && (
              <Pressable
                accessibilityRole="link"
                accessibilityLabel="Open in your browser"
                onPress={() => openInBrowser(link)}
                android_ripple={{ color: colors.divider }}
                style={styles.actionTarget}
              >
                <Text style={styles.action}>Open</Text>
                <ExternalLink size={ICON.badge} color={colors.primary} />
              </Pressable>
            )}
          </View>
        </View>

        <ScrollView
          scrollEnabled={expanded}
          contentContainerStyle={[styles.below, { paddingBottom: space.lg + (keyboard > 0 ? 0 : insets.bottom) }]}
          keyboardShouldPersistTaps="handled"
        >
          <Card>
            <Text style={styles.title}>{resource.title}</Text>
            <Text style={styles.muted}>
              {kindLabel(resource.kind)}
              {resource.reference ? ` · ${resource.reference}` : ""}
            </Text>
            <Button
              label={done ? "Done · tap to undo" : "Mark as done"}
              variant={done ? "secondary" : "primary"}
              busy={update.isPending}
              onPress={() => update.mutate({ id: resource.id, completed: !done })}
            />
            {update.isError && <ErrorText error={update.error} />}
          </Card>

          <Field
            label="Your answer (write in German)"
            value={answer}
            onChangeText={setAnswer}
            multiline
            maxLength={600}
            autoCapitalize="sentences"
          />
          <Button
            label="Check my answer"
            variant="secondary"
            busy={check.isPending}
            disabled={!answer.trim()}
            onPress={() => check.mutate({ text: answer.trim() }, { onSuccess: setResult })}
          />
          {check.isError && <ErrorText error={check.error} />}
          {result && <CheckResultView result={result} onDecided={decided} />}

          <Button label="Stuck? Scan the exercise for hints" variant="secondary" onPress={() => router.push("/scanner")} />
        </ScrollView>
      </Animated.View>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  player: { position: "absolute", top: 0, left: 0, right: 0, backgroundColor: colors.surface },
  web: { flex: 1 },
  loading: { ...StyleSheet.absoluteFill, alignItems: "center", justifyContent: "center" },
  problem: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.surface,
    color: colors.warning,
    fontSize: 13,
    paddingHorizontal: space.lg,
    paddingVertical: space.sm,
  },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    backgroundColor: colors.background,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderColor: colors.cardBorder,
    boxShadow: `0 -6px 24px ${colors.shadow}`,
  },
  handleArea: { height: HANDLE_HEIGHT, alignItems: "center", justifyContent: "center", gap: 2 },
  grabber: { width: 36, height: 4, borderRadius: 2, backgroundColor: colors.divider },
  handleLabel: { fontSize: 13, lineHeight: 18, fontWeight: "700", color: colors.muted },
  actions: {
    height: ACTIONS_HEIGHT,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: space.lg,
  },
  actionTarget: { minHeight: TOUCH, flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: space.xs },
  iconTarget: { width: TOUCH, height: TOUCH, alignItems: "center", justifyContent: "center" },
  action: { color: colors.primary, fontSize: 15, lineHeight: 22, fontWeight: "700" },
  actionOff: { color: colors.muted, fontWeight: "400" },
  below: { padding: space.lg, gap: space.md },
  title: { fontSize: 17, lineHeight: 24, fontWeight: "800" },
  muted: { fontSize: 14, lineHeight: 20, color: colors.muted },
}));
