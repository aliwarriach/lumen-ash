import { useEffect, useState } from "react";
import { AccessibilityInfo } from "react-native";
import {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";

/**
 * True when the learner has turned on Android's "Remove animations". Anything that moves (sheets,
 * the drawer, celebrations) should then appear in place instead.
 */
export function useReduceMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((on) => alive && setReduce(on))
      .catch(() => {});
    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", setReduce);
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);
  return reduce;
}

/** How long things take to move, in ms. */
export const DURATION = { short: 160, medium: 240 } as const;

/**
 * A short "pop" (grow, settle back) each time `active` turns on: the right answer, a new badge.
 * Returns a style for an `Animated.View`. With "Remove animations" on, nothing moves.
 */
export function usePop(active: boolean) {
  const reduce = useReduceMotion();
  const scale = useSharedValue(1);
  useEffect(() => {
    if (!active || reduce) return;
    scale.value = withSequence(
      withTiming(1.12, { duration: 120, easing: Easing.out(Easing.quad) }),
      withSpring(1, { damping: 8, stiffness: 220 }),
    );
  }, [active, reduce, scale]);
  return useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
}

/** A quick side-to-side shake each time `active` turns on: a wrong answer. Still when motion is off. */
export function useShake(active: boolean) {
  const reduce = useReduceMotion();
  const x = useSharedValue(0);
  useEffect(() => {
    if (!active || reduce) return;
    x.value = withSequence(
      withTiming(-6, { duration: 50 }),
      withRepeat(withTiming(6, { duration: 100 }), 3, true),
      withTiming(0, { duration: 50 }),
    );
  }, [active, reduce, x]);
  return useAnimatedStyle(() => ({ transform: [{ translateX: x.value }] }));
}
