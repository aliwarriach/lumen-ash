import { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";

import { winHaptic } from "@/ui/haptics";
import { useReduceMotion } from "@/ui/motion";
import { useTheme } from "@/ui/theme";

const PARTICLES = 14;
const DURATION = 1000;

/**
 * A one-off burst of colored specks from the middle of its parent, with a success buzz. It plays
 * once when it appears, so mount it only for a real win (a finished session, a perfect round). It
 * covers its parent without catching touches. With "Remove animations" on there is no burst; the
 * buzz and the screen's own words still say it went well.
 */
export function Celebration() {
  const reduce = useReduceMotion();
  const colors = useTheme();
  const palette = [
    colors.primary,
    colors.illustration.amber,
    colors.illustration.pink,
    colors.illustration.teal,
    colors.done,
  ];
  useEffect(() => winHaptic(), []);
  if (reduce) return null;
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" importantForAccessibility="no-hide-descendants">
      {Array.from({ length: PARTICLES }, (_, i) => (
        <Speck key={i} index={i} color={palette[i % palette.length]!} />
      ))}
    </View>
  );
}

function Speck({ index, color }: { index: number; color: string }) {
  const t = useSharedValue(0);
  // Spread evenly round the circle; every other speck flies further so it is not a ring.
  const angle = (index / PARTICLES) * 2 * Math.PI;
  const distance = index % 2 === 0 ? 120 : 80;
  useEffect(() => {
    t.value = withDelay(index * 15, withTiming(1, { duration: DURATION, easing: Easing.out(Easing.cubic) }));
  }, [index, t]);
  const style = useAnimatedStyle(() => ({
    opacity: 1 - t.value,
    transform: [
      { translateX: Math.cos(angle) * distance * t.value },
      { translateY: Math.sin(angle) * distance * t.value + 40 * t.value * t.value },
      { scale: 1 - 0.4 * t.value },
    ],
  }));
  return <Animated.View style={[styles.speck, { backgroundColor: color }, style]} />;
}

const styles = StyleSheet.create({
  // Centered in the parent: left/top 50% put the corner there, the margin moves it back.
  speck: { position: "absolute", left: "50%", top: "50%", width: 10, height: 10, marginLeft: -5, marginTop: -5, borderRadius: 3 },
});
