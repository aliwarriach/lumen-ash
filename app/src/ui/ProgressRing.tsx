import { useEffect, type ReactNode } from "react";
import { View } from "react-native";
import Animated, {
  Easing,
  useAnimatedProps,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import Svg, { Circle } from "react-native-svg";

import { useReduceMotion } from "@/ui/motion";
import { makeStyles, useTheme } from "@/ui/theme";

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

type Props = {
  /** 0 to 1. */
  value: number;
  /** What is inside the ring, e.g. "2/5". */
  children?: ReactNode;
  /** Read out instead of the drawing, e.g. "2 of 5 done". */
  label: string;
  size?: number;
  stroke?: number;
  color?: string;
};

/**
 * A circular progress ring that starts at the top and goes clockwise. It sweeps to its value when
 * the screen opens and whenever the value changes (unless "Remove animations" is on).
 */
export function ProgressRing({ value, children, label, size = 84, stroke = 8, color }: Props) {
  const colors = useTheme();
  const styles = useStyles();
  const reduce = useReduceMotion();
  const r = (size - stroke) / 2;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  const share = Math.max(0, Math.min(1, value));

  const shown = useSharedValue(reduce ? share : 0);
  useEffect(() => {
    shown.value = reduce ? share : withTiming(share, { duration: 700, easing: Easing.out(Easing.cubic) });
  }, [share, reduce, shown]);

  // The whole circle is one dash; sliding it round with the offset draws the arc.
  const arc = useAnimatedProps(() => ({
    strokeDashoffset: circumference * (1 - shown.value),
    strokeOpacity: shown.value > 0.001 ? 1 : 0,
  }));

  return (
    <View
      style={[styles.ring, { width: size, height: size }]}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(share * 100) }}
    >
      <Svg width={size} height={size} style={styles.svg}>
        <Circle cx={c} cy={c} r={r} fill="none" stroke={colors.divider} strokeWidth={stroke} />
        <AnimatedCircle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke={color ?? colors.primary}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circumference} ${circumference}`}
          animatedProps={arc}
          transform={`rotate(-90 ${c} ${c})`}
        />
      </Svg>
      {children}
    </View>
  );
}

const useStyles = makeStyles(() => ({
  ring: { alignItems: "center", justifyContent: "center" },
  svg: { position: "absolute", top: 0, left: 0 },
}));
