import { BlurTargetView, BlurView } from "expo-blur";
import { createContext, useContext, useRef, type ComponentRef, type ReactNode, type RefObject } from "react";
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Defs, Ellipse, RadialGradient, Stop } from "react-native-svg";

import { makeStyles, radius, space, useTheme } from "@/ui/theme";

/**
 * Glass: frosted cards over a soft backdrop of large color patches.
 *
 * The backdrop is drawn once, already soft (radial gradients, no live blur), inside a blur target.
 * Glass cards blur that target with expo-blur. On Android a BlurView only blurs what is inside a
 * `BlurTargetView` whose ref it is given, so a screen wraps its content in `<Backdrop>`, which
 * provides the target to every `<Glass>` inside it. Outside a Backdrop a Glass card falls back to
 * its translucent color, which looks almost the same over a plain page.
 *
 * Keep glass rare (the main card and the plan list): each one is a live blur.
 */

type Target = RefObject<ComponentRef<typeof View> | null>;

const BlurTarget = createContext<Target | null>(null);

/** Where the patches sit, as fractions of the screen: indigo, teal, amber, pink. */
const PATCHES = [
  { cx: 0.1, cy: 0.06, rx: 0.75, ry: 0.32 },
  { cx: 0.95, cy: 0.22, rx: 0.6, ry: 0.28 },
  { cx: 0.05, cy: 0.62, rx: 0.6, ry: 0.26 },
  { cx: 0.9, cy: 0.9, rx: 0.7, ry: 0.3 },
] as const;

/** The page with its color patches. Children are drawn above it, and may use `<Glass>`. */
export function Backdrop({ children }: { children: ReactNode }) {
  const colors = useTheme();
  const target = useRef<ComponentRef<typeof View> | null>(null);
  return (
    <View style={[styles.fill, { backgroundColor: colors.background }]}>
      <BlurTargetView ref={target} style={StyleSheet.absoluteFill} pointerEvents="none">
        <Svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
          <Defs>
            {colors.backdrop.map((color, i) => (
              <RadialGradient key={color} id={`patch${i}`} cx="50%" cy="50%" r="50%">
                <Stop offset="0" stopColor={color} stopOpacity={colors.backdropOpacity} />
                <Stop offset="0.55" stopColor={color} stopOpacity={colors.backdropOpacity * 0.45} />
                <Stop offset="1" stopColor={color} stopOpacity={0} />
              </RadialGradient>
            ))}
          </Defs>
          {PATCHES.map((p, i) => (
            <Ellipse
              key={i}
              cx={p.cx * 100}
              cy={p.cy * 100}
              rx={p.rx * 100}
              ry={p.ry * 100}
              fill={`url(#patch${i})`}
            />
          ))}
        </Svg>
      </BlurTargetView>
      <BlurTarget.Provider value={target}>{children}</BlurTarget.Provider>
    </View>
  );
}

type GlassProps = {
  children: ReactNode;
  /** Padding and gap inside the card. */
  style?: StyleProp<ViewStyle>;
  /** Corner radius: cards 28 (default), the nav bar or a sheet may pass their own. */
  rounded?: number;
  /** Makes the whole card a button, with a ripple. Give it a label for screen readers. */
  onPress?: () => void;
  accessibilityLabel?: string;
  accessibilityHint?: string;
};

/** A frosted glass card: blur, translucent fill, thin bright edge, soft shadow. */
export function Glass({ children, style, rounded = radius.card, onPress, accessibilityLabel, accessibilityHint }: GlassProps) {
  const colors = useTheme();
  const glass = useStyles();
  const target = useContext(BlurTarget);
  return (
    // The shadow sits on an outer view: the inner one clips the blur to the rounded corners.
    <View style={[glass.shadow, { borderRadius: rounded }]}>
      <View style={[glass.clip, { borderRadius: rounded }]}>
        {target && (
          <BlurView
            blurTarget={target}
            blurMethod="dimezisBlurView"
            intensity={40}
            tint={colors.scheme}
            style={StyleSheet.absoluteFill}
          />
        )}
        {onPress ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={accessibilityLabel}
            accessibilityHint={accessibilityHint}
            onPress={onPress}
            android_ripple={{ color: colors.divider }}
            style={[glass.body, style]}
          >
            {children}
          </Pressable>
        ) : (
          <View style={[glass.body, style]}>{children}</View>
        )}
      </View>
    </View>
  );
}

/** Glass that fills its parent edge to edge, e.g. behind the bottom navigation bar. */
export function GlassFill({ color }: { color: string }) {
  const colors = useTheme();
  const target = useContext(BlurTarget);
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {target && (
        <BlurView
          blurTarget={target}
          blurMethod="dimezisBlurView"
          intensity={40}
          tint={colors.scheme}
          style={StyleSheet.absoluteFill}
        />
      )}
      <View style={[StyleSheet.absoluteFill, { backgroundColor: color }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
});

const useStyles = makeStyles((colors) => ({
  shadow: { boxShadow: `0 8px 32px ${colors.shadow}` },
  clip: { overflow: "hidden", borderWidth: 1, borderColor: colors.cardBorder },
  // The translucent fill is drawn over the blur, which is what gives glass its frosted tint.
  body: { backgroundColor: colors.card, padding: space.lg + space.xs, gap: space.md },
}));
